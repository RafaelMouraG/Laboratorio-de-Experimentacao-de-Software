"""RQ 09, análise 2: métricas DORA antes × depois do primeiro commit com IA (#118).

Execute da raiz do repositório com ``python -m lab03.analise.rq09_antes_depois``. Sem rede: as
releases saem do export ``releases_detalhe.jsonl.gz`` (uma linha por release da janela, com os
commits do compare) e os runs, do ``runs.csv``. Os caminhos podem ser trocados por argumento.

Divisão: o instante ``t0`` é o ``primeiro_commit_ia`` do ``repos.csv``. Release publicada antes de
``t0`` fica no "antes"; publicada em ``t0`` ou depois, no "depois" (o mesmo "inclusive" da
``proporcao_ia_desde_adocao``). Run vai pelo início (``run_started_at``, ou ``created_at`` sem ele),
a mesma data que ``falhas.py`` usa para ordenar. Cada lado é tratado como uma janela própria pelas
funções de ``lab03/metricas``: a frequência divide pela duração do lado, em dias inteiros, como na
janela inteira; um episódio de falha aberto em ``t0`` fica censurado no "antes", e no "depois" a
falha anterior ao primeiro sucesso não tem início conhecido. Repositório criado durante a janela
tem o "antes" contado a partir do dia da criação.

Mínimos para um repositório entrar (``DIAS_MINIMOS``, ``MINIMO_RELEASES``, ``MINIMO_RUNS``):

* pelo menos 91 dias (um trimestre) de cada lado de ``t0`` dentro da janela. O
  ``primeiro_commit_ia`` só olha commits da janela, então um repositório que já usava IA antes de
  outubro de 2025 aparece "adotando" nos primeiros dias; exigir um trimestre sem nenhum rastro antes
  de ``t0`` afasta os casos mais óbvios, e do lado de depois garante um trimestre de uso;
* nas métricas de release (frequência e lead time), pelo menos 3 releases de cada lado;
* nas de CI (CFR (a) e recuperação), pelo menos 30 runs válidos de cada lado.

Depois disso, cada métrica pareia só os repositórios com valor dos dois lados (lead time sem release
avaliável ou recuperação sem episódio fechado ficam vazios). Com menos de ``MINIMO_PARES`` pares o
Wilcoxon não roda: com 5 pares o menor p bilateral exato já é 0,0625.

Tendência: o tempo de cada repositório é contado em trimestres de 91 dias a partir de ``t0``
(trimestre 0 começa em ``t0``, o -1 termina nele). Cada métrica é calculada por repositório e
trimestre, recortado à janela, e o Mann-Kendall roda sobre a mediana entre repositórios de cada
trimestre. Trimestre com menos de 28 dias na janela ou com menos de ``MINIMO_REPOS_TRIMESTRE``
repositórios fica fora.
"""

from __future__ import annotations

import argparse
import logging
import math
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import pymannkendall  # noqa: E402
from statsmodels.stats.multitest import multipletests  # noqa: E402

from lab03.analise.comum import DADOS, SAIDA, salvar_figura, salvar_tabela  # noqa: E402
from lab03.analise.estatistica import wilcoxon_pareado  # noqa: E402
from lab03.metricas.falhas import cfr_ci, classificar, tempo_recuperacao  # noqa: E402
from lab03.metricas.frequencia import releases_por_semana  # noqa: E402
from lab03.metricas.lead_time import lead_time_por_commit, lead_time_por_release  # noqa: E402
from lab03.pipeline.__main__ import carregar_config  # noqa: E402

ALFA = 0.05
NAN = float("nan")
ANTES, DEPOIS = "antes", "depois"
DIAS_MINIMOS = 91
SENSIBILIDADE_DIAS = (56, 91, 120)
MINIMO_RELEASES = 3
MINIMO_RUNS = 30
MINIMO_PARES = 6
TRIMESTRE = timedelta(days=91)
DIAS_MINIMOS_TRIMESTRE = 28
MINIMO_REPOS_TRIMESTRE = 5
RELEASES_DETALHE = DADOS / "para_athos" / "releases_detalhe.jsonl.gz"
COLUNAS_RUNS = ["repo", "id", "workflow_id", "conclusion", "created_at", "run_started_at", "updated_at"]

# métrica → (de onde vem, nome no artigo, escala log no gráfico)
METRICAS = {
    "releases_por_semana": ("releases", "Releases por semana", True),
    "lead_time_release_horas": ("releases", "Lead time (a), horas", True),
    "lead_time_commit_horas": ("releases", "Lead time (b), horas", True),
    "cfr_ci": ("runs", "CFR (a)", False),
    "recuperacao_horas": ("runs", "Recuperação, horas", True),
}

log = logging.getLogger(__name__)


# ---------- divisão ----------

def _utc(valor) -> pd.Timestamp:
    momento = pd.Timestamp(valor)
    return momento.tz_localize("UTC") if momento.tzinfo is None else momento.tz_convert("UTC")


def limites_janela(inicio: date | str, fim: date | str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Primeiro e último instante da janela inclusiva, em UTC."""
    comeco = datetime.combine(pd.Timestamp(inicio).date(), time.min, tzinfo=timezone.utc)
    final = datetime.combine(pd.Timestamp(fim).date(), time.max, tzinfo=timezone.utc)
    return pd.Timestamp(comeco), pd.Timestamp(final)


def inicio_run(runs: pd.DataFrame) -> pd.Series:
    """Instante de cada run: ``run_started_at``, ou ``created_at`` quando ele falta."""
    return pd.to_datetime(runs["run_started_at"].fillna(runs["created_at"]), utc=True)


def recortar(releases: pd.DataFrame, runs: pd.DataFrame, de, ate) -> tuple[list[dict], list[dict]]:
    """Releases publicadas e runs iniciados em ``[de, ate)``, já como dicts para ``lab03/metricas``."""
    rel = releases[(releases["published_at"] >= de) & (releases["published_at"] < ate)]
    run = runs[(runs["inicio"] >= de) & (runs["inicio"] < ate)]
    return rel.to_dict("records"), run.to_dict("records")


# ---------- métricas de um período ----------

def metricas_periodo(releases: list[dict], runs: list[dict], de: pd.Timestamp, ate: pd.Timestamp) -> dict:
    """Métricas DORA de ``[de, ate)``, cada uma pela função de ``lab03/metricas``.

    ``ate`` é exclusivo; para ``releases_por_semana`` (inclusiva nos dois lados) ele vira o último
    microssegundo antes, e a duração sai em dias inteiros, como na janela inteira.
    """
    ultimo = (ate - pd.Timedelta(microseconds=1)).to_pydatetime()
    datas = [r["published_at"] for r in releases]
    por_release = lead_time_por_release(releases)
    por_commit = lead_time_por_commit(releases)
    recuperacao = tempo_recuperacao(runs)
    return {
        "dias": (ultimo.date() - de.date()).days,
        "releases": len(releases),
        "runs_validos": sum(classificar(r.get("conclusion")) is not None for r in runs),
        "releases_por_semana": releases_por_semana(datas, de.to_pydatetime(), ultimo)
        if ultimo.date() > de.date() else None,
        "lead_time_release_horas": por_release.mediana_horas,
        "lead_time_release_avaliadas": por_release.valores,
        "lead_time_commit_horas": por_commit.mediana_horas,
        "lead_time_commit_avaliadas": por_commit.valores,
        "cfr_ci": cfr_ci(runs),
        "recuperacao_horas": recuperacao.mediana_horas,
        "recuperacao_fechados": recuperacao.episodios - recuperacao.censurados,
    }


def antes_depois(repo: str, t0, releases: pd.DataFrame, runs: pd.DataFrame, inicio, fim) -> list[dict]:
    """Duas linhas, antes e depois de ``t0``, dentro da janela ``[inicio, fim]`` (datas inclusivas)."""
    comeco, final = limites_janela(inicio, fim)
    depois_do_fim = final + pd.Timedelta(microseconds=1)
    t0 = _utc(t0)
    linhas = []
    for periodo, de, ate in ((ANTES, comeco, t0), (DEPOIS, t0, depois_do_fim)):
        rel, run = recortar(releases, runs, de, ate)
        linhas.append({"repo": repo, "primeiro_commit_ia": t0, "periodo": periodo,
                       **metricas_periodo(rel, run, de, ate)})
    return linhas


def por_trimestre(repo: str, t0, releases: pd.DataFrame, runs: pd.DataFrame, inicio, fim) -> list[dict]:
    """Uma linha por trimestre de 91 dias contado a partir de ``t0``, recortado à janela.

    Trimestre com menos de ``DIAS_MINIMOS_TRIMESTRE`` dias dentro da janela não entra.
    """
    comeco, final = limites_janela(inicio, fim)
    depois_do_fim = final + pd.Timedelta(microseconds=1)
    t0 = _utc(t0)
    primeiro = math.floor((comeco - t0) / TRIMESTRE)
    ultimo = math.floor((final - t0) / TRIMESTRE)
    linhas = []
    for k in range(primeiro, ultimo + 1):
        de = max(t0 + k * TRIMESTRE, comeco)
        ate = min(t0 + (k + 1) * TRIMESTRE, depois_do_fim)
        if (ate - de) < pd.Timedelta(days=DIAS_MINIMOS_TRIMESTRE):
            continue
        rel, run = recortar(releases, runs, de, ate)
        linhas.append({"repo": repo, "trimestre": k, **metricas_periodo(rel, run, de, ate)})
    return linhas


# ---------- elegibilidade e funil ----------

def largo(por_periodo: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por repositório, colunas ``<campo>_antes`` e ``<campo>_depois``."""
    tabela = por_periodo.pivot(index="repo", columns="periodo")
    tabela.columns = [f"{campo}_{periodo}" for campo, periodo in tabela.columns]
    return tabela


def elegiveis(
    por_periodo: pd.DataFrame,
    dias: int = DIAS_MINIMOS,
    minimo_releases: int = MINIMO_RELEASES,
    minimo_runs: int = MINIMO_RUNS,
) -> pd.DataFrame:
    """Por repositório, se ele passa no mínimo de dias e nos mínimos de releases e de runs.

    ``releases`` e ``runs`` já incluem o mínimo de dias.
    """
    t = largo(por_periodo)
    passa_dias = (t[f"dias_{ANTES}"] >= dias) & (t[f"dias_{DEPOIS}"] >= dias)
    passa_releases = (t[f"releases_{ANTES}"] >= minimo_releases) & (t[f"releases_{DEPOIS}"] >= minimo_releases)
    passa_runs = (t[f"runs_validos_{ANTES}"] >= minimo_runs) & (t[f"runs_validos_{DEPOIS}"] >= minimo_runs)
    return pd.DataFrame({
        "dias": passa_dias,
        "releases": passa_dias & passa_releases,
        "runs": passa_dias & passa_runs,
    })


def funil(repos: pd.DataFrame, por_periodo: pd.DataFrame, inicio, fim, dias: int = DIAS_MINIMOS) -> pd.DataFrame:
    """Quantos repositórios chegam a cada etapa e por que os outros ficaram de fora.

    As duas últimas etapas partem da etapa dos dias, cada uma para o seu grupo de métricas.
    """
    comeco, final = limites_janela(inicio, fim)
    t0 = pd.to_datetime(repos["primeiro_commit_ia"], utc=True)
    adotantes = int(t0.notna().sum())
    na_janela = int(((t0 >= comeco) & (t0 <= final)).sum())
    t = largo(por_periodo)
    antes_ok = int((t[f"dias_{ANTES}"] >= dias).sum())
    ok = elegiveis(por_periodo, dias)
    linhas = [
        ("repositórios no repos.csv", len(repos), 0, ""),
        ("com algum commit com IA", adotantes, len(repos) - adotantes, "nenhum commit com IA na janela"),
        ("primeiro commit com IA dentro da janela", na_janela, adotantes - na_janela,
         "primeiro commit com IA fora da janela"),
        (f"pelo menos {dias} dias antes da adoção", antes_ok, na_janela - antes_ok,
         f"menos de {dias} dias entre o início da janela (ou a criação do repositório) e a adoção"),
        (f"pelo menos {dias} dias depois da adoção", int(ok["dias"].sum()), antes_ok - int(ok["dias"].sum()),
         f"adoção nos últimos {dias} dias da janela"),
        (f"métricas de release: {MINIMO_RELEASES}+ releases de cada lado", int(ok["releases"].sum()),
         int(ok["dias"].sum() - ok["releases"].sum()), f"menos de {MINIMO_RELEASES} releases em algum lado"),
        (f"métricas de CI: {MINIMO_RUNS}+ runs válidos de cada lado", int(ok["runs"].sum()),
         int(ok["dias"].sum() - ok["runs"].sum()), f"menos de {MINIMO_RUNS} runs válidos em algum lado"),
    ]
    return pd.DataFrame(linhas, columns=["etapa", "restantes", "descartados", "motivo"])


# ---------- testes ----------

def parear(por_periodo: pd.DataFrame, metrica: str, repos: Iterable[str]) -> dict:
    """Wilcoxon pareado depois × antes de ``metrica`` nos ``repos`` com valor dos dois lados.

    Efeito positivo: a métrica tende a ser maior depois da adoção.
    """
    t = largo(por_periodo)
    t = t[t.index.isin(list(repos))]
    pares = t[[f"{metrica}_{ANTES}", f"{metrica}_{DEPOIS}"]].astype(float).dropna()
    antes, depois = pares[f"{metrica}_{ANTES}"], pares[f"{metrica}_{DEPOIS}"]
    linha = {
        "metrica": metrica,
        "n": len(pares),
        "mediana_antes": antes.median(),
        "mediana_depois": depois.median(),
        "mediana_diferenca": (depois - antes).median(),
        "subiram": int((depois > antes).sum()),
        "desceram": int((depois < antes).sum()),
        "empates": int((depois == antes).sum()),
        "estatistica": NAN, "p_valor": NAN, "efeito": NAN, "nome_efeito": "rank_biserial",
    }
    if len(pares) < MINIMO_PARES:
        return linha
    try:
        teste = wilcoxon_pareado(depois.tolist(), antes.tolist())
    except ValueError:  # todos os pares empatados
        return linha
    linha.update(estatistica=teste["estatistica"], p_valor=teste["p_valor"], efeito=teste["efeito"])
    return linha


def holm(tabela: pd.DataFrame) -> pd.DataFrame:
    tabela = tabela.copy()
    tabela["p_ajustado"] = float("nan")
    tabela["significativo"] = False
    testados = tabela["p_valor"].notna()
    if testados.any():
        rejeita, ajustado, _, _ = multipletests(tabela.loc[testados, "p_valor"].astype(float),
                                                alpha=ALFA, method="holm")
        tabela.loc[testados, "p_ajustado"] = ajustado
        tabela.loc[testados, "significativo"] = rejeita
    return tabela


def comparar(por_periodo: pd.DataFrame, dias: int = DIAS_MINIMOS) -> pd.DataFrame:
    """Uma linha por métrica, com Holm sobre as cinco."""
    ok = elegiveis(por_periodo, dias)
    linhas = [parear(por_periodo, metrica, ok.index[ok[fonte]]) for metrica, (fonte, _, _) in METRICAS.items()]
    return holm(pd.DataFrame(linhas))


def mann_kendall(serie: pd.Series) -> dict:
    """Mann-Kendall original sobre a série ordenada pelo índice; vazio com menos de 3 pontos."""
    valores = serie.dropna().sort_index()
    linha = {"pontos": len(valores), "tendencia": None, "tau": None, "s": None, "p_valor": None,
             "inclinacao_sen": None}
    if len(valores) < 3:
        return linha
    teste = pymannkendall.original_test(valores.to_numpy(), alpha=ALFA)
    linha.update(tendencia=teste.trend, tau=float(teste.Tau), s=float(teste.s),
                 p_valor=float(teste.p), inclinacao_sen=float(teste.slope))
    return linha


def tendencias(trimestres: pd.DataFrame, ok: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(mediana por métrica e trimestre, Mann-Kendall por métrica)."""
    medianas, testes = [], []
    for metrica, (fonte, _, _) in METRICAS.items():
        dados = trimestres[trimestres["repo"].isin(ok.index[ok[fonte]])].dropna(subset=[metrica])
        resumo = dados.groupby("trimestre")[metrica].agg(repos="count", mediana="median").reset_index()
        resumo.insert(0, "metrica", metrica)
        resumo["no_teste"] = resumo["repos"] >= MINIMO_REPOS_TRIMESTRE
        medianas.append(resumo)
        serie = resumo[resumo["no_teste"]].set_index("trimestre")["mediana"]
        testes.append({"metrica": metrica,
                       "primeiro_trimestre": serie.index.min() if len(serie) else None,
                       "ultimo_trimestre": serie.index.max() if len(serie) else None,
                       **mann_kendall(serie)})
    medianas = [m for m in medianas if len(m)] or medianas[:1]
    return pd.concat(medianas, ignore_index=True), pd.DataFrame(testes)


# ---------- figura ----------

def figura(por_periodo: pd.DataFrame, medianas: pd.DataFrame, ok: pd.DataFrame):
    fig, eixos = plt.subplots(2, len(METRICAS), figsize=(3.2 * len(METRICAS), 6.2))
    t = largo(por_periodo)
    for coluna, (metrica, (fonte, nome, log_escala)) in enumerate(METRICAS.items()):
        cima, baixo = eixos[0, coluna], eixos[1, coluna]
        pares = t.loc[t.index.isin(ok.index[ok[fonte]]), [f"{metrica}_{ANTES}", f"{metrica}_{DEPOIS}"]]
        pares = pares.astype(float).dropna()
        if log_escala:
            pares = pares[(pares > 0).all(axis=1)]
            cima.set_yscale("log")
        for _, (a, d) in pares.iterrows():
            cima.plot([0, 1], [a, d], color="0.75", linewidth=0.6)
        cima.plot([0, 1], pares.median().to_numpy(), color="black", linewidth=2, marker="o")
        cima.set_xticks([0, 1], ["antes", "depois"])
        cima.set_xlim(-0.2, 1.2)
        cima.set_title(f"{nome}\n(n = {len(pares)})", fontsize=9)

        serie = medianas[(medianas["metrica"] == metrica) & medianas["no_teste"]]
        baixo.plot(serie["trimestre"], serie["mediana"], color="black", marker="s", linestyle="-")
        for _, ponto in serie.iterrows():
            baixo.annotate(str(int(ponto["repos"])), (ponto["trimestre"], ponto["mediana"]),
                           textcoords="offset points", xytext=(0, 6), ha="center", fontsize=7)
        baixo.margins(y=0.15)
        baixo.axvline(-0.5, color="black", linestyle="--", linewidth=0.8)
        baixo.set_xlabel("trimestre desde a adoção")
        if coluna == 0:
            cima.set_ylabel("valor por repositório")
            baixo.set_ylabel("mediana entre repositórios\n(número = repositórios)")
    fig.tight_layout()
    return fig


# ---------- dados ----------

def carregar_releases(caminho: Path, repos: set[str], tags: dict[str, set[str]] | None = None) -> pd.DataFrame:
    """Releases do export, só dos ``repos`` pedidos e, se ``tags`` vier, só as do ``releases.csv``."""
    partes = []
    with pd.read_json(caminho, lines=True, chunksize=2000, dtype=False, convert_dates=False) as leitor:
        for bloco in leitor:
            bloco = bloco[bloco["repo"].isin(repos)][["repo", "tag_name", "published_at", "sem_anterior", "commits"]]
            partes.append(bloco)
    releases = pd.concat(partes, ignore_index=True)
    if tags is not None:
        releases = releases[[t in tags.get(r, set()) for r, t in zip(releases["repo"], releases["tag_name"])]]
    releases["published_at"] = pd.to_datetime(releases["published_at"], utc=True)
    return releases


def carregar_runs(caminho: Path, repos: set[str]) -> pd.DataFrame:
    partes = []
    for bloco in pd.read_csv(caminho, usecols=COLUNAS_RUNS, chunksize=500_000):
        partes.append(bloco[bloco["repo"].isin(repos)])
    runs = pd.concat(partes, ignore_index=True)
    runs["inicio"] = inicio_run(runs)
    runs["run_started_at"] = runs["inicio"]
    runs["updated_at"] = pd.to_datetime(runs["updated_at"], utc=True)
    return runs.drop(columns=["created_at"])


def calcular(repos: pd.DataFrame, releases: pd.DataFrame, runs: pd.DataFrame, inicio, fim
             ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(antes/depois por repositório, trimestres por repositório) dos adotantes dentro da janela.

    Repositório criado durante a janela começa no dia da criação: antes dele não havia o que medir,
    e contar esses dias derrubaria a frequência do "antes".
    """
    comeco, final = limites_janela(inicio, fim)
    t0 = pd.to_datetime(repos["primeiro_commit_ia"], utc=True)
    criado = pd.to_datetime(repos["criado_em"], utc=True).dt.normalize()
    adotantes = repos.assign(t0=t0, comeco=criado.clip(lower=comeco))[(t0 >= comeco) & (t0 <= final)]
    rel_por_repo = dict(tuple(releases.groupby("repo")))
    run_por_repo = dict(tuple(runs.groupby("repo")))
    vazio_rel, vazio_run = releases.iloc[0:0], runs.iloc[0:0]
    periodos, trimestres = [], []
    for i, linha in enumerate(adotantes.itertuples(), start=1):
        rel = rel_por_repo.get(linha.repo, vazio_rel)
        run = run_por_repo.get(linha.repo, vazio_run)
        periodos.extend(antes_depois(linha.repo, linha.t0, rel, run, linha.comeco, fim))
        trimestres.extend(por_trimestre(linha.repo, linha.t0, rel, run, linha.comeco, fim))
        if i % 25 == 0:
            log.info("%d/%d repositórios", i, len(adotantes))
    return pd.DataFrame(periodos), pd.DataFrame(trimestres)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lab03.analise.rq09_antes_depois", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="lab03/config.yaml")
    parser.add_argument("--dados", type=Path, default=DADOS, help="pasta com repos.csv e releases.csv")
    parser.add_argument("--releases", type=Path, default=RELEASES_DETALHE, help="releases_detalhe.jsonl.gz")
    parser.add_argument("--runs", type=Path, default=None, help="runs.csv (padrão: <dados>/runs.csv)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    janela = carregar_config(args.config)
    inicio, fim = janela["inicio"], janela["fim"]
    repos = pd.read_csv(args.dados / "repos.csv")
    alvo = set(repos.loc[repos["primeiro_commit_ia"].notna(), "repo"])
    tags = pd.read_csv(args.dados / "releases.csv").groupby("repo")["tag_name"].agg(set).to_dict()
    log.info("lendo releases de %s", args.releases)
    releases = carregar_releases(args.releases, alvo, tags)
    log.info("lendo runs")
    runs = carregar_runs(args.runs or args.dados / "runs.csv", alvo)

    por_periodo, trimestres = calcular(repos, releases, runs, inicio, fim)
    ok = elegiveis(por_periodo)
    tabela = comparar(por_periodo)
    etapas = funil(repos, por_periodo, inicio, fim)
    medianas, testes_mk = tendencias(trimestres, ok)
    sensibilidade = pd.concat(
        [comparar(por_periodo, dias).assign(dias_minimos=dias) for dias in SENSIBILIDADE_DIAS],
        ignore_index=True,
    )[["dias_minimos", "metrica", "n", "mediana_antes", "mediana_depois", "p_valor", "p_ajustado", "efeito"]]

    salvar_tabela(tabela, "rq09_antes_depois")
    salvar_tabela(etapas, "rq09_antes_depois_funil")
    salvar_tabela(testes_mk, "rq09_antes_depois_mann_kendall")
    salvar_tabela(medianas, "rq09_antes_depois_trimestres")
    salvar_tabela(sensibilidade, "rq09_antes_depois_sensibilidade")
    SAIDA.mkdir(parents=True, exist_ok=True)
    por_periodo.join(ok.add_prefix("entra_"), on="repo").to_csv(SAIDA / "rq09_antes_depois_por_repo.csv", index=False)
    fig = figura(por_periodo, medianas, ok)
    salvar_figura(fig, "rq09_antes_depois")
    plt.close(fig)

    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print("RQ 09, análise 2: antes × depois do primeiro commit com IA")
        print(etapas.to_string(index=False))
        print(tabela.to_string(index=False))
        print(testes_mk.to_string(index=False))
        print(sensibilidade.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""RQ 09, análise 3: commits com IA × sem IA dentro do mesmo repositório (#119).

Execute da raiz do repositório com ``python -m lab03.analise.rq09_commits [--rede]``.

Cada commit do branch principal na janela é ligado às execuções de CI que ele disparou
(``head_sha`` do ``runs.csv``) e à primeira release que o entregou (commits do compare de cada
release). As listas de commits saem do cache da coleta, sem rede; com ``--rede``, o que faltar no
cache é baixado com o ``GITHUB_TOKEN`` do ``.env``. Repositório sem cache fica fora e é contado.

Só entram na comparação os commits a partir do primeiro commit com IA do repositório, o mesmo
período da ``proporcao_ia_desde_adocao``, para os dois grupos dividirem a mesma fase do projeto.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from typing import Iterable

import pandas as pd
from statsmodels.stats.multitest import multipletests

from lab03.analise.comum import DADOS, RAIZ, SAIDA, salvar_tabela
from lab03.analise.estatistica import wilcoxon_pareado
from lab03.metricas.corretiva import falhas_por_release
from lab03.metricas.falhas import FALHA, classificar
from lab03.metricas.frequencia import _data
from lab03.pipeline import adocao, releases
from lab03.pipeline.__main__ import carregar_config
from lab03.pipeline.api import GitHubAPI

ALFA = 0.05
COM_IA = "com_ia"
SEM_IA = "sem_ia"
# Commits com a medida, em cada grupo, para o repositório entrar no pareamento daquela medida.
MINIMO_COMMITS = 5

# medida → coluna com quantos commits a medida tem, no agregado por repositório
MEDIDAS = {
    "lead_time_horas": "n_lead_time",
    "falhou_ci": "n_ci",
    "release_falhou": "n_release",
}
NOMES_MEDIDAS = {
    "lead_time_horas": "Lead time (b), horas (mediana)",
    "falhou_ci": "Commits com falha de CI (proporção)",
    "release_falhou": "Commits em release seguida de corretiva (proporção)",
}

log = logging.getLogger(__name__)


# ---------- ligação ----------

def ligar_releases(lista_releases: Iterable[dict], fim: date | str) -> dict[str, dict]:
    """sha → primeira release que entregou o commit, com o lead time dele e se ela falhou.

    Um commit pode estar no compare de mais de uma release (linhas de versão diferentes, compare
    contra uma release antiga); vale a publicada primeiro, que é quando ele chegou ao usuário.
    ``release_falhou`` segue a CFR (b): None para release censurada. Lead time negativo (commit
    com data depois da release) fica None, como os descartados de ``lead_time.py``.
    """
    ligacao: dict[str, dict] = {}
    for release, falhou in falhas_por_release(lista_releases, fim):
        publicada = _data(release["published_at"])
        for commit in release["commits"]:
            if commit["sha"] in ligacao:
                continue
            horas = (publicada - _data(commit["data"])).total_seconds() / 3600
            ligacao[commit["sha"]] = {
                "tag_name": release["tag_name"],
                "lead_time_horas": horas if horas >= 0 else None,
                "release_falhou": falhou,
            }
    return ligacao


def ligar_runs(runs: pd.DataFrame) -> pd.DataFrame:
    """Runs válidos e de falha por ``head_sha``, pela tabela de conclusões da CFR (a).

    Um commit pode ter vários runs (um por workflow, ou um novo run do mesmo workflow); todos
    contam. Conclusões fora da tabela (cancelled, skipped etc.) não entram.
    """
    tipos = runs["conclusion"].map(classificar)
    validos = runs.assign(falha=tipos == FALHA)[tipos.notna()]
    return validos.groupby("head_sha").agg(runs_validos=("falha", "size"), runs_falha=("falha", "sum"))


def tabela_commits(
    repo: str,
    commits: list[dict],
    ligacao: dict[str, dict],
    runs_por_sha: pd.DataFrame,
    ferramentas: dict[str, str],
) -> pd.DataFrame:
    """Uma linha por commit da janela, com as três medidas.

    ``ferramentas`` leva o sha de cada commit com IA do repositório às ferramentas dele, separadas
    por ``;``. ``falhou_ci`` e ``release_falhou`` são 1/0, vazios quando o commit não tem run
    válido ou release avaliada, para a média dar a proporção.
    """
    df = pd.DataFrame(commits, columns=["sha", "data"])
    df.insert(0, "repo", repo)
    df["data"] = pd.to_datetime(df["data"], utc=True)
    df["ferramentas"] = df["sha"].map(ferramentas)
    df["com_ia"] = df["ferramentas"].notna()
    primeiro = df.loc[df["com_ia"], "data"].min()
    df["desde_adocao"] = df["data"] >= primeiro if df["com_ia"].any() else False

    liga = pd.DataFrame.from_dict(ligacao, orient="index",
                                  columns=["tag_name", "lead_time_horas", "release_falhou"])
    df = df.join(liga, on="sha")
    df["lead_time_horas"] = df["lead_time_horas"].astype(float)
    df["release_falhou"] = df["release_falhou"].map({True: 1.0, False: 0.0})

    df = df.join(runs_por_sha, on="sha")
    df[["runs_validos", "runs_falha"]] = df[["runs_validos", "runs_falha"]].fillna(0).astype(int)
    df["falhou_ci"] = (df["runs_falha"] > 0).astype(float).where(df["runs_validos"] > 0)
    return df


# ---------- comparação ----------

def agregar(commits: pd.DataFrame, grupo: pd.Series) -> pd.DataFrame:
    """Uma linha por repositório × grupo; linhas com ``grupo`` vazio ficam de fora."""
    return (
        commits.assign(grupo=grupo)
        .dropna(subset=["grupo"])
        .groupby(["repo", "grupo"])
        .agg(
            commits=("sha", "size"),
            lead_time_horas=("lead_time_horas", "median"),
            n_lead_time=("lead_time_horas", "count"),
            falhou_ci=("falhou_ci", "mean"),
            n_ci=("falhou_ci", "count"),
            release_falhou=("release_falhou", "mean"),
            n_release=("release_falhou", "count"),
        )
        .reset_index()
    )


def parear(agregado: pd.DataFrame, medida: str, minimo: int = MINIMO_COMMITS) -> dict:
    """Wilcoxon pareado ``com_ia`` × ``sem_ia`` nos repositórios com ``minimo`` commits nos dois.

    Sem nenhum par com diferença, o teste fica vazio e só sai a contagem.
    """
    n = MEDIDAS[medida]
    suficientes = agregado[agregado[n] >= minimo]
    largo = suficientes.pivot(index="repo", columns="grupo", values=medida)
    largo = largo.reindex(columns=[COM_IA, SEM_IA]).dropna()
    linha = {
        "medida": medida,
        "repos": len(largo),
        "mediana_com_ia": largo[COM_IA].median(),
        "mediana_sem_ia": largo[SEM_IA].median(),
        "mediana_diferenca": (largo[COM_IA] - largo[SEM_IA]).median(),
    }
    try:
        teste = wilcoxon_pareado(largo[COM_IA].tolist(), largo[SEM_IA].tolist())
    except ValueError:
        teste = {"n": len(largo), "empates": len(largo), "estatistica": None, "p_valor": None,
                 "efeito": None, "nome_efeito": "rank_biserial"}
    return {**linha, **{chave: valor for chave, valor in teste.items() if chave != "n"}}


def grupo_por_ferramenta(commits: pd.DataFrame, ferramenta: str) -> pd.Series:
    """``com_ia`` para os commits da ferramenta, ``sem_ia`` para os sem IA; os de outra ferramenta
    ficam vazios. Um commit com rastro de duas ferramentas entra nas duas."""
    da_ferramenta = commits["ferramentas"].fillna("").str.split(";").map(lambda lista: ferramenta in lista)
    return pd.Series(
        [COM_IA if sim else (SEM_IA if not ia else None)
         for sim, ia in zip(da_ferramenta, commits["com_ia"])],
        index=commits.index, dtype=object,
    )


def comparar(commits: pd.DataFrame, minimo: int = MINIMO_COMMITS) -> pd.DataFrame:
    """As três medidas com todas as ferramentas juntas e depois por ferramenta.

    Holm separado em cada família: as 3 comparações principais e as das ferramentas.
    """
    periodo = commits[commits["desde_adocao"]]
    recortes = {"todas": periodo["com_ia"].map({True: COM_IA, False: SEM_IA})}
    nomes = sorted({f for lista in periodo["ferramentas"].dropna() for f in lista.split(";")})
    recortes.update({nome: grupo_por_ferramenta(periodo, nome) for nome in nomes})

    linhas = []
    for recorte, grupo in recortes.items():
        agregado = agregar(periodo, grupo)
        linhas.extend({"recorte": recorte, **parear(agregado, medida, minimo)} for medida in MEDIDAS)
    tabela = pd.DataFrame(linhas)
    tabela["familia"] = tabela["recorte"].where(tabela["recorte"] == "todas", "ferramenta")
    tabela["p_ajustado"] = float("nan")
    tabela["significativo"] = False
    for _, indices in tabela[tabela["p_valor"].notna()].groupby("familia").groups.items():
        rejeita, ajustado, _, _ = multipletests(tabela.loc[indices, "p_valor"], alpha=ALFA, method="holm")
        tabela.loc[indices, "p_ajustado"] = ajustado
        tabela.loc[indices, "significativo"] = rejeita
    return tabela


def cobertura(commits: pd.DataFrame) -> pd.DataFrame:
    """Quantos commits ficaram sem run ou sem release ligada, na janela e desde a adoção."""
    recortes = {
        "janela": commits,
        f"desde_adocao_{COM_IA}": commits[commits["desde_adocao"] & commits["com_ia"]],
        f"desde_adocao_{SEM_IA}": commits[commits["desde_adocao"] & ~commits["com_ia"]],
    }
    linhas = []
    for nome, df in recortes.items():
        com_release = df["tag_name"].notna()
        linhas.append({
            "recorte": nome,
            "commits": len(df),
            "sem_run": int((df["runs_validos"] == 0).sum()),
            "com_dois_runs_ou_mais": int((df["runs_validos"] >= 2).sum()),
            "sem_release": int((~com_release).sum()),
            "release_censurada": int((com_release & df["release_falhou"].isna()).sum()),
            "lead_time_negativo": int((com_release & df["lead_time_horas"].isna()).sum()),
        })
    return pd.DataFrame(linhas)


# ---------- dados ----------

class ForaDoCache(Exception):
    """Página que não está no cache, numa execução sem ``--rede``.

    Não herda de ``ErroAPI`` de propósito: ``adocao.listar_commits`` anota um ``ErroAPI`` como
    falha da API em ``_adocao_falhas.json``, e isto não é falha da API.
    """


class SoCache(GitHubAPI):
    """``GitHubAPI`` que só lê o cache."""

    def __init__(self, pasta_cache):
        super().__init__("", pasta_cache)

    def _buscar(self, caminho: str, params) -> dict:
        raise ForaDoCache(caminho)


def ferramentas_por_sha(commits_ia: pd.DataFrame) -> dict[str, dict[str, str]]:
    """repo → sha → ferramentas do commit, em ordem alfabética e separadas por ``;``."""
    juntas = commits_ia.groupby(["repo", "sha"])["ferramenta"].agg(lambda f: ";".join(sorted(set(f))))
    return {repo: grupo.droplevel(0).to_dict() for repo, grupo in juntas.groupby(level=0)}


def carregar_commits(
    api: GitHubAPI, repos: pd.DataFrame, runs: pd.DataFrame, commits_ia: pd.DataFrame,
    tags_releases: dict[str, set[str]], inicio: date, fim: date,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tabela de commits de todos os repositórios e a situação de cada repositório.

    Só valem as releases de ``tags_releases`` (as do ``releases.csv``): a lista de releases do cache
    pode ter sido baixada em outro dia, e uma release republicada muda de data (no PostHog, a
    ``posthog-live-latest`` entrava na janela com um compare de 9.745 commits).
    """
    runs_por_repo = dict(tuple(runs.groupby("repo")))
    ia = ferramentas_por_sha(commits_ia)
    vazio = pd.DataFrame(columns=["runs_validos", "runs_falha"])
    tabelas, situacoes = [], []
    for i, linha in enumerate(repos.itertuples(), start=1):
        try:
            lista_releases = [
                release for release in releases.coletar(api, linha.repo, inicio, fim)["releases"]
                if release["tag_name"] in tags_releases.get(linha.repo, set())
            ]
            commits, _ = adocao.listar_commits(api, linha.repo, linha.default_branch, inicio, fim)
        except ForaDoCache as erro:
            log.warning("%d/%d %s: %s não está no cache, fica fora", i, len(repos), linha.repo, erro)
            situacoes.append({"repo": linha.repo, "situacao": "sem_cache"})
            continue
        runs_repo = runs_por_repo.get(linha.repo)
        tabelas.append(tabela_commits(
            linha.repo, commits, ligar_releases(lista_releases, fim),
            vazio if runs_repo is None else ligar_runs(runs_repo), ia.get(linha.repo, {}),
        ))
        # todo repositório da amostra tem pelo menos 50 runs; nenhum no runs.csv é arquivo incompleto
        situacoes.append({"repo": linha.repo, "situacao": "sem_runs_no_csv" if runs_repo is None else "ok"})
    return pd.concat(tabelas, ignore_index=True), pd.DataFrame(situacoes)


def funil(situacoes: pd.DataFrame, commits: pd.DataFrame) -> pd.DataFrame:
    adotantes = commits.loc[commits["com_ia"], "repo"].nunique()
    contagem = situacoes["situacao"].value_counts()
    return pd.DataFrame([
        {"etapa": "repositórios no repos.csv", "repos": len(situacoes)},
        {"etapa": "sem cache de releases ou commits", "repos": int(contagem.get("sem_cache", 0))},
        {"etapa": "sem nenhum run no runs.csv (falha de CI vazia)",
         "repos": int(contagem.get("sem_runs_no_csv", 0))},
        {"etapa": "com pelo menos um commit com IA", "repos": int(adotantes)},
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lab03.analise.rq09_commits", description=__doc__)
    parser.add_argument("--config", default="lab03/config.yaml")
    parser.add_argument("--rede", action="store_true", help="baixa o que faltar no cache")
    parser.add_argument("--minimo", type=int, default=MINIMO_COMMITS,
                        help="commits com a medida em cada grupo para o repositório entrar no pareamento")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    # `adocao.listar_commits` avisa cada intervalo que deu 500 na coleta; aqui é ruído
    logging.getLogger("lab03.pipeline.adocao").setLevel(logging.ERROR)

    config = carregar_config(args.config)
    pasta_cache = RAIZ.parent / config.get("pasta_cache", "lab03/data/cache")
    api = GitHubAPI.do_ambiente(pasta_cache) if args.rede else SoCache(pasta_cache)

    repos = pd.read_csv(DADOS / "repos.csv")
    runs = pd.read_csv(DADOS / "runs.csv", usecols=["repo", "head_sha", "conclusion"])
    commits_ia = pd.read_csv(DADOS / "commits_ia.csv")
    tags_releases = pd.read_csv(DADOS / "releases.csv").groupby("repo")["tag_name"].agg(set).to_dict()
    commits, situacoes = carregar_commits(api, repos, runs, commits_ia, tags_releases,
                                          config["inicio"], config["fim"])

    tabela = comparar(commits, args.minimo)
    alcance = cobertura(commits)
    etapas = funil(situacoes, commits)
    periodo = commits[commits["desde_adocao"]]
    agregado = agregar(periodo, periodo["com_ia"].map({True: COM_IA, False: SEM_IA}))

    salvar_tabela(tabela, "rq09_commits_pareado")
    salvar_tabela(alcance, "rq09_commits_cobertura")
    salvar_tabela(etapas, "rq09_commits_funil")
    SAIDA.mkdir(parents=True, exist_ok=True)
    agregado.to_csv(SAIDA / "rq09_commits_por_repo.csv", index=False)

    print("RQ 09, análise 3: commits com IA × sem IA, pareado por repositório")
    print(etapas.to_string(index=False))
    print(alcance.to_string(index=False))
    colunas = ["recorte", "medida", "repos", "mediana_com_ia", "mediana_sem_ia", "p_valor", "p_ajustado", "efeito"]
    print(tabela[colunas].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

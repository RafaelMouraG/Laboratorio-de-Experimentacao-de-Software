"""Junta as etapas da coleta num fluxo só, em duas fases.

1. **Triagem.** Os candidatos, do mais estrelado para baixo, passam pelos filtros baratos (data de
   criação, Actions, metadados, nº de releases e nº de runs pelo `total_count`) até a amostra chegar
   no limite. Já grava `repos.csv` e `funil.csv`: a amostra final fica conhecida em poucas horas.
2. **Coleta pesada.** Compare de cada release e lista completa dos runs, só para quem passou. É
   onde vai quase toda a cota.

Cada fase deixa um marcador por repo em `pasta_cache/<owner>__<repo>/` (`_triagem` e `_completo`)
com o resultado. Na próxima execução ele é lido de lá sem passar pela API; um repo interrompido no
meio não tem o marcador e é refeito, mas as páginas já baixadas saem do cache da `GitHubAPI`.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Iterable, Optional

from lab03.metricas.corretiva import eh_corretiva
from lab03.metricas.falhas import classificar
from lab03.metricas.repositorio import CAMPOS_METRICAS, metricas_do_repo
from lab03.pipeline import metadados, releases, runs
from lab03.pipeline.api import ErroAPI, GitHubAPI, RecursoAusente
from lab03.pipeline.selecao import MOTIVO_SEM_ACTIONS, Funil, candidatos_por_estrelas, total_na_busca, usa_actions

MIN_RELEASES = 5
MIN_RUNS_VALIDOS = 50
MARCADOR_TRIAGEM = "_triagem"
MARCADOR = "_completo"

# (chave, nome no funil), na ordem em que o pipeline aplica. "coleta" só descarta na fase pesada.
ETAPAS = (
    ("criacao", "criados antes do início da janela"),
    ("actions", "com GitHub Actions"),
    ("metadados", "metadados coletados"),
    ("releases", f">= {MIN_RELEASES} releases na janela"),
    ("runs", f">= {MIN_RUNS_VALIDOS} runs válidos na janela"),
    ("coleta", "compare e runs coletados"),
)
MOTIVO_NAO_AVALIADO = "nao_avaliado_amostra_completa"
MOTIVO_CRIADO_NA_JANELA = "criado_na_janela"  # a RQ 01 divide por 52 semanas que ele não viveu
MOTIVO_POUCAS_RELEASES = f"menos_de_{MIN_RELEASES}_releases"
MOTIVO_POUCOS_RUNS = f"menos_de_{MIN_RUNS_VALIDOS}_runs"
MOTIVO_INACESSIVEL = "inacessivel"  # 404/409: apagado, bloqueado ou vazio depois da busca
MOTIVO_ERRO_API = "erro_api"  # 4xx que não é cota, ex.: 403 de repo bloqueado por DMCA

CAMPOS_REPOS = (
    "repo", "estrelas", "linguagem", "default_branch", "criado_em", "idade_anos", "contribuidores",
    "releases", "releases_sem_anterior", "releases_ignoradas_compare_404", "commits_releases",
    "runs_validos", "runs_sucesso", "runs_falha",
)
CAMPOS_RELEASES = (
    "repo", "tag_name", "published_at", "prerelease", "html_url", "commits",
    "sem_anterior", "ignorada_compare_404", "eh_corretiva",
)
CAMPOS_RUNS = ("repo", *runs.CAMPOS, "classe")
CAMPOS_TAGS = ("repo", "nome", "sha", "data")

log = logging.getLogger(__name__)


# ---------- marcadores de repo terminado ----------

def pasta_repo(pasta_cache: str | Path, repo: str) -> Path:
    """Mesma pasta em que a `GitHubAPI` guarda as respostas do repo."""
    return Path(pasta_cache) / repo.replace("/", "__")


def ler_marcador(
    pasta_cache: str | Path, repo: str, assinatura: dict, nome: str = MARCADOR
) -> Optional[dict]:
    """Resultado salvo, ou None se o repo não terminou a fase ou foi coletado com outra configuração."""
    arquivo = pasta_repo(pasta_cache, repo) / nome
    if not arquivo.exists():
        return None
    try:
        conteudo = json.loads(arquivo.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.warning("%s: marcador %s corrompido, refazendo", repo, nome)
        return None
    if conteudo.get("assinatura") != assinatura:
        log.info("%s: marcador %s de outra configuração, refazendo", repo, nome)
        return None
    return conteudo["resultado"]


def gravar_marcador(
    pasta_cache: str | Path, repo: str, assinatura: dict, resultado: dict, nome: str = MARCADOR
) -> None:
    arquivo = pasta_repo(pasta_cache, repo) / nome
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    tmp = arquivo.with_suffix(".tmp")
    tmp.write_text(json.dumps({"assinatura": assinatura, "resultado": resultado}, ensure_ascii=False),
                   encoding="utf-8")
    os.replace(tmp, arquivo)


# ---------- um repo ----------

def _descartado(repo: str, etapa: str, motivo: str) -> dict:
    return {"repo": repo, "aceito": False, "etapa": etapa, "motivo": motivo}


def _descarte_por_erro(repo: str, etapa: str, erro: Exception) -> dict:
    """404/409 e outros 4xx viram descarte na etapa em que aconteceram. Falha de rede que esgotou
    as tentativas (`ErroAPI` com status 0) sobe, para o repo não ser marcado como terminado."""
    if isinstance(erro, ErroAPI) and erro.status < 400:
        raise erro
    log.warning("%s: %s, descartando", repo, erro)
    return _descartado(repo, etapa, MOTIVO_INACESSIVEL if isinstance(erro, RecursoAusente) else MOTIVO_ERRO_API)


def criado_na_janela(criado_em: str, inicio: date) -> bool:
    """Criado depois de 00:00 UTC do primeiro dia da janela."""
    criado = datetime.fromisoformat(criado_em.replace("Z", "+00:00"))
    return criado > datetime.combine(inicio, time.min, timezone.utc)


def triar_repo(api: GitHubAPI, candidato: dict, inicio: date, fim: date) -> dict:
    """Filtros baratos, parando no primeiro que descarta. A data de criação vem do item da busca,
    então quem nasceu dentro da janela cai sem nenhuma chamada à API."""
    repo = candidato["full_name"]
    if criado_na_janela(candidato["created_at"], inicio):
        return _descartado(repo, "criacao", MOTIVO_CRIADO_NA_JANELA)
    etapa = "actions"
    try:
        if not usa_actions(api, repo):
            return _descartado(repo, etapa, MOTIVO_SEM_ACTIONS)

        etapa = "metadados"
        meta = metadados.coletar_metadados(api, repo, fim)

        etapa = "releases"
        na_janela = len(releases.releases_na_janela(releases.listar_releases(api, repo), inicio, fim))
        if na_janela < MIN_RELEASES:
            return _descartado(repo, etapa, MOTIVO_POUCAS_RELEASES)

        etapa = "runs"
        validos = runs.contar_validos_na_janela(api, repo, meta["default_branch"], inicio, fim,
                                                minimo=MIN_RUNS_VALIDOS)
        if validos < MIN_RUNS_VALIDOS:
            return _descartado(repo, etapa, MOTIVO_POUCOS_RUNS)
    except (RecursoAusente, ErroAPI) as erro:
        return _descarte_por_erro(repo, etapa, erro)

    return {"repo": repo, "aceito": True, "etapa": None, "motivo": None, "metadados": meta,
            "releases_janela": na_janela}


def coletar_repo(
    api: GitHubAPI, triado: dict, inicio: date, fim: date, coletar_tags: bool = False
) -> dict:
    """Parte cara, só para quem passou na triagem: commits de cada release e todos os runs."""
    repo, meta = triado["repo"], triado["metadados"]
    try:
        coleta_releases = releases.coletar(api, repo, inicio, fim, coletar_tags=coletar_tags)
        lista_runs = runs.listar_runs(api, repo, meta["default_branch"], inicio, fim)
    except (RecursoAusente, ErroAPI) as erro:
        return _descarte_por_erro(repo, "coleta", erro)

    validos = [run for run in lista_runs if classificar(run.get("conclusion"))]
    if len(validos) < MIN_RUNS_VALIDOS:
        # só acontece se o total_count da triagem e a lista discordarem (run que mudou entre as duas)
        log.warning("%s: a triagem passou, mas a lista completa tem %d runs válidos", repo, len(validos))
        return _descartado(repo, "runs", MOTIVO_POUCOS_RUNS)

    return {
        "repo": repo,
        "aceito": True,
        "etapa": None,
        "motivo": None,
        "metadados": meta,
        "releases": coleta_releases["releases"],
        "tags": coleta_releases["tags"],
        "runs": validos,
        "runs_censurados": len(lista_runs) - len(validos),
    }


def avaliar_repo(
    api: GitHubAPI, candidato: dict, inicio: date, fim: date, coletar_tags: bool = False
) -> dict:
    """As duas fases seguidas para um candidato (o item da busca)."""
    triado = triar_repo(api, candidato, inicio, fim)
    return coletar_repo(api, triado, inicio, fim, coletar_tags) if triado["aceito"] else triado


# ---------- funil ----------

def montar_funil(total_busca: int, resultados: Iterable[dict], limite: int, estrelas_minimas: int) -> Funil:
    """Cada linha é a anterior menos os descartados dela.

    A busca acha muito mais repositórios do que o necessário. Eles são avaliados em ordem de
    estrelas e a avaliação para quando a amostra chega no `limite`; os que sobraram entram como
    `nao_avaliado_amostra_completa` na segunda linha.
    """
    resultados = list(resultados)
    funil = Funil()
    funil.registrar(f"repositórios na busca (>= {estrelas_minimas} estrelas, sem fork e arquivados)",
                    total_busca, {})
    restantes = len(resultados)
    nao_avaliados = total_busca - restantes
    funil.registrar("avaliados em ordem de estrelas", restantes,
                    {MOTIVO_NAO_AVALIADO: nao_avaliados} if nao_avaliados > 0 else {})
    for chave, nome in ETAPAS:
        motivos: dict[str, int] = {}
        for r in resultados:
            if r["etapa"] == chave:
                motivos[r["motivo"]] = motivos.get(r["motivo"], 0) + 1
        restantes -= sum(motivos.values())
        funil.registrar(nome, restantes, motivos)
    funil.registrar(f"amostra final (limite {limite})", restantes, {})
    return funil


# ---------- CSVs ----------

def _escrever_csv(caminho: Path, campos: Iterable[str], linhas: Iterable[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(campos), extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(linhas)


def linha_repo(resultado: dict) -> dict:
    """Depois só da triagem, saem os metadados e o nº de releases; as contagens que dependem da
    coleta pesada ficam vazias."""
    if "releases" not in resultado:
        return {**resultado["metadados"], "releases": resultado["releases_janela"]}
    lista_releases, lista_runs = resultado["releases"], resultado["runs"]
    classes = [classificar(run["conclusion"]) for run in lista_runs]
    return {
        **resultado["metadados"],
        "releases": len(lista_releases),
        "releases_sem_anterior": sum(r["sem_anterior"] for r in lista_releases),
        "releases_ignoradas_compare_404": sum(r["ignorada_compare_404"] for r in lista_releases),
        "commits_releases": sum(len(r["commits"]) for r in lista_releases),
        "runs_validos": len(lista_runs),
        "runs_sucesso": classes.count("sucesso"),
        "runs_falha": classes.count("falha"),
    }


def salvar_triagem(pasta_saida: str | Path, aceitos: list[dict], funil: Funil) -> None:
    pasta = Path(pasta_saida)
    _escrever_csv(pasta / "repos.csv", CAMPOS_REPOS, (linha_repo(r) for r in aceitos))
    funil.salvar(pasta / "funil.csv")


def salvar_csvs(
    pasta_saida: str | Path,
    aceitos: list[dict],
    funil: Funil,
    coletar_tags: bool,
    inicio: date | None = None,
    fim: date | None = None,
) -> None:
    """Grava os CSVs da coleta e, quando há janela, o dataset agregado de métricas."""
    pasta = Path(pasta_saida)
    salvar_triagem(pasta, aceitos, funil)
    # com `so_concluidos`, quem ainda não passou pela coleta pesada só aparece no repos.csv
    coletados = [r for r in aceitos if "releases" in r]
    _escrever_csv(
        pasta / "releases.csv",
        CAMPOS_RELEASES,
        (
            {
                **rel,
                "repo": r["repo"],
                "commits": len(rel["commits"]),
                "eh_corretiva": eh_corretiva(rel),
            }
            for r in coletados
            for rel in r["releases"]
        ),
    )
    _escrever_csv(
        pasta / "runs.csv",
        CAMPOS_RUNS,
        ({**run, "repo": r["repo"], "classe": classificar(run["conclusion"])} for r in coletados for run in r["runs"]),
    )
    if inicio is not None and fim is not None:
        _escrever_csv(
            pasta / "metricas.csv",
            CAMPOS_METRICAS,
            (metricas_do_repo(r, inicio, fim) for r in aceitos),
        )
    if coletar_tags:
        _escrever_csv(pasta / "tags.csv", CAMPOS_TAGS,
                      ({**tag, "repo": r["repo"]} for r in coletados for tag in r["tags"] or []))


# ---------- fluxo completo ----------

def _cota(api: GitHubAPI) -> str:
    return "?" if api.restante is None else str(api.restante)


def _situacao(resultado: dict) -> str:
    return "aceito" if resultado["aceito"] else f"descartado: {resultado['motivo']}"


def executar(
    api: GitHubAPI,
    estrelas_minimas: int,
    inicio: date,
    fim: date,
    limite: int,
    pasta_cache: str | Path,
    pasta_saida: str | Path,
    coletar_tags: bool = False,
    so_triagem: bool = False,
    so_concluidos: bool = False,
) -> Funil:
    """Triagem até `limite` aceitos e, se não for `so_triagem`, a coleta pesada deles.

    `so_concluidos` grava os CSVs só com os repositórios que já têm o marcador da coleta pesada,
    sem chamar a API para os outros: serve para trabalhar com o que já saiu enquanto a coleta roda.
    Os pendentes ficam no repos.csv com as contagens vazias, como depois da triagem.
    """
    janela = {"inicio": str(inicio), "fim": str(fim)}
    # com outros campos de release (ex.: o `body` da #96), o marcador antigo é refeito a partir do cache
    assinatura = {**janela, "coletar_tags": coletar_tags, "campos_release": list(releases.CAMPOS_RELEASE)}
    total = total_na_busca(api, estrelas_minimas)
    log.info("%d repositórios na busca; triagem até %d na amostra", total, limite)

    triados: list[dict] = []
    aceitos: list[dict] = []
    for i, candidato in enumerate(candidatos_por_estrelas(api, estrelas_minimas), start=1):
        if len(aceitos) >= limite:
            break
        repo = candidato["full_name"]
        resultado = ler_marcador(pasta_cache, repo, janela, MARCADOR_TRIAGEM)
        if resultado is None:
            resultado = triar_repo(api, candidato, inicio, fim)
            gravar_marcador(pasta_cache, repo, janela, resultado, MARCADOR_TRIAGEM)
            log.info("triagem %d %s -> %s | amostra %d/%d | cota %s",
                     i, repo, _situacao(resultado), len(aceitos) + resultado["aceito"], limite, _cota(api))
        triados.append(resultado)
        if resultado["aceito"]:
            aceitos.append(resultado)

    if len(aceitos) < limite:
        log.warning("candidatos acabaram com %d de %d repositórios na amostra", len(aceitos), limite)
    funil = montar_funil(total, triados, limite, estrelas_minimas)
    salvar_triagem(pasta_saida, aceitos, funil)
    log.info("triagem pronta: %d repositórios em %s/repos.csv", len(aceitos), pasta_saida)
    if so_triagem:
        return funil

    completos: dict[str, dict] = {}
    for i, triado in enumerate(aceitos, start=1):
        repo = triado["repo"]
        resultado = ler_marcador(pasta_cache, repo, assinatura)
        if resultado is None and so_concluidos:
            continue
        if resultado is None:
            log.info("coleta %d/%d %s | cota %s", i, len(aceitos), repo, _cota(api))
            resultado = coletar_repo(api, triado, inicio, fim, coletar_tags)
            gravar_marcador(pasta_cache, repo, assinatura, resultado)
            log.info("coleta %d/%d %s -> %s | cota %s", i, len(aceitos), repo, _situacao(resultado), _cota(api))
        completos[repo] = resultado

    if so_concluidos:
        log.info("%d de %d repositórios com a coleta pesada concluída", len(completos), len(aceitos))
    finais = [completos.get(r["repo"], r) for r in triados]
    funil = montar_funil(total, finais, limite, estrelas_minimas)
    salvar_csvs(
        pasta_saida,
        [r for r in finais if r["aceito"]],
        funil,
        coletar_tags,
        inicio,
        fim,
    )
    return funil

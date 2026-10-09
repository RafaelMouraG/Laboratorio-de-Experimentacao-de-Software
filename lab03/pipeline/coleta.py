"""Junta as etapas da coleta num fluxo só, repo a repo, até a amostra chegar no limite.

Cada repo avaliado (aceito ou descartado) ganha `pasta_cache/<owner>__<repo>/_completo`, um JSON
com o resultado. Na próxima execução ele é lido de lá sem passar pela API; um repo interrompido no
meio não tem o marcador e é refeito, mas as páginas já baixadas saem do cache da `GitHubAPI`.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Iterable, Optional

from lab03.metricas.falhas import classificar
from lab03.pipeline import metadados, releases, runs
from lab03.pipeline.api import ErroAPI, GitHubAPI, RecursoAusente
from lab03.pipeline.selecao import MOTIVO_SEM_ACTIONS, Funil, buscar_candidatos, usa_actions

MIN_RELEASES = 5
MIN_RUNS_VALIDOS = 50
MARCADOR = "_completo"

# (chave, nome no funil), na ordem em que o pipeline aplica
ETAPAS = (
    ("actions", "com GitHub Actions"),
    ("metadados", "metadados coletados"),
    ("releases", f">= {MIN_RELEASES} releases na janela"),
    ("runs", f">= {MIN_RUNS_VALIDOS} runs válidos na janela"),
)
MOTIVO_POUCAS_RELEASES = f"menos_de_{MIN_RELEASES}_releases"
MOTIVO_POUCOS_RUNS = f"menos_de_{MIN_RUNS_VALIDOS}_runs"
MOTIVO_INACESSIVEL = "inacessivel"  # 404/409: apagado, bloqueado ou vazio depois da busca
MOTIVO_ERRO_API = "erro_api"  # 4xx que não é cota, ex.: 403 de repo bloqueado por DMCA
MOTIVO_LIMITE = "nao_avaliado_limite_atingido"

CAMPOS_REPOS = (
    "repo", "estrelas", "linguagem", "default_branch", "criado_em", "idade_anos", "contribuidores",
    "releases", "releases_sem_anterior", "releases_ignoradas_compare_404", "commits_releases",
    "runs_validos", "runs_sucesso", "runs_falha",
)
CAMPOS_RELEASES = (
    "repo", "tag_name", "published_at", "prerelease", "html_url", "commits",
    "sem_anterior", "ignorada_compare_404",
)
CAMPOS_RUNS = ("repo", *runs.CAMPOS, "classe")
CAMPOS_TAGS = ("repo", "nome", "sha", "data")

log = logging.getLogger(__name__)


# ---------- marcador de repo terminado ----------

def pasta_repo(pasta_cache: str | Path, repo: str) -> Path:
    """Mesma pasta em que a `GitHubAPI` guarda as respostas do repo."""
    return Path(pasta_cache) / repo.replace("/", "__")


def ler_marcador(pasta_cache: str | Path, repo: str, assinatura: dict) -> Optional[dict]:
    """Resultado salvo, ou None se o repo não terminou ou foi coletado com outra configuração."""
    arquivo = pasta_repo(pasta_cache, repo) / MARCADOR
    if not arquivo.exists():
        return None
    try:
        conteudo = json.loads(arquivo.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.warning("%s: marcador corrompido, refazendo", repo)
        return None
    if conteudo.get("assinatura") != assinatura:
        log.info("%s: marcador de outra configuração, refazendo", repo)
        return None
    return conteudo["resultado"]


def gravar_marcador(pasta_cache: str | Path, repo: str, assinatura: dict, resultado: dict) -> None:
    arquivo = pasta_repo(pasta_cache, repo) / MARCADOR
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    tmp = arquivo.with_suffix(".tmp")
    tmp.write_text(json.dumps({"assinatura": assinatura, "resultado": resultado}, ensure_ascii=False),
                   encoding="utf-8")
    os.replace(tmp, arquivo)


# ---------- um repo ----------

def _descartado(repo: str, etapa: str, motivo: str) -> dict:
    return {"repo": repo, "aceito": False, "etapa": etapa, "motivo": motivo}


def avaliar_repo(
    api: GitHubAPI, repo: str, inicio: date, fim: date, coletar_tags: bool = False
) -> dict:
    """Passa o repo pelas etapas e para na primeira que o descarta.

    404/409 e outros 4xx viram descarte na etapa em que aconteceram. Falha de rede que esgotou as
    tentativas (`ErroAPI` com status 0) sobe, para o repo não ser marcado como terminado.
    """
    etapa = "actions"
    try:
        if not usa_actions(api, repo):
            return _descartado(repo, etapa, MOTIVO_SEM_ACTIONS)

        etapa = "metadados"
        meta = metadados.coletar_metadados(api, repo, fim)

        etapa = "releases"
        todas = releases.listar_releases(api, repo)
        if len(releases.releases_na_janela(todas, inicio, fim)) < MIN_RELEASES:
            return _descartado(repo, etapa, MOTIVO_POUCAS_RELEASES)
        coleta_releases = releases.coletar(api, repo, inicio, fim, coletar_tags=coletar_tags)

        etapa = "runs"
        lista_runs = runs.listar_runs(api, repo, meta["default_branch"], inicio, fim)
        if runs.contar_validos(lista_runs) < MIN_RUNS_VALIDOS:
            return _descartado(repo, etapa, MOTIVO_POUCOS_RUNS)
    except RecursoAusente as erro:
        log.warning("%s: %s, descartando", repo, erro)
        return _descartado(repo, etapa, MOTIVO_INACESSIVEL)
    except ErroAPI as erro:
        if erro.status < 400:
            raise
        log.warning("%s: %s, descartando", repo, erro)
        return _descartado(repo, etapa, MOTIVO_ERRO_API)

    return {
        "repo": repo,
        "aceito": True,
        "etapa": None,
        "motivo": None,
        "metadados": meta,
        "releases": coleta_releases["releases"],
        "tags": coleta_releases["tags"],
        "runs": [run for run in lista_runs if classificar(run.get("conclusion"))],
    }


# ---------- funil ----------

def montar_funil(total_candidatos: int, resultados: Iterable[dict], limite: int) -> Funil:
    """Conta, para cada etapa, quantos repos passaram e por que os outros caíram.

    A amostra para no `limite`, então os candidatos depois do último avaliado entram como
    `nao_avaliado_limite_atingido` na linha final.
    """
    resultados = list(resultados)
    funil = Funil()
    funil.registrar("candidatos da busca", total_candidatos, {})
    restantes = len(resultados)
    for chave, nome in ETAPAS:
        motivos: dict[str, int] = {}
        for r in resultados:
            if r["etapa"] == chave:
                motivos[r["motivo"]] = motivos.get(r["motivo"], 0) + 1
        restantes -= sum(motivos.values())
        funil.registrar(nome, restantes, motivos)
    nao_avaliados = total_candidatos - len(resultados)
    funil.registrar(f"amostra final (limite {limite})", restantes,
                    {MOTIVO_LIMITE: nao_avaliados} if nao_avaliados else {})
    return funil


# ---------- CSVs ----------

def _escrever_csv(caminho: Path, campos: Iterable[str], linhas: Iterable[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(campos), extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(linhas)


def linha_repo(resultado: dict) -> dict:
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


def salvar_csvs(pasta_saida: str | Path, aceitos: list[dict], funil: Funil, coletar_tags: bool) -> None:
    pasta = Path(pasta_saida)
    _escrever_csv(pasta / "repos.csv", CAMPOS_REPOS, (linha_repo(r) for r in aceitos))
    _escrever_csv(
        pasta / "releases.csv",
        CAMPOS_RELEASES,
        ({**rel, "repo": r["repo"], "commits": len(rel["commits"])} for r in aceitos for rel in r["releases"]),
    )
    _escrever_csv(
        pasta / "runs.csv",
        CAMPOS_RUNS,
        ({**run, "repo": r["repo"], "classe": classificar(run["conclusion"])} for r in aceitos for run in r["runs"]),
    )
    if coletar_tags:
        _escrever_csv(pasta / "tags.csv", CAMPOS_TAGS,
                      ({**tag, "repo": r["repo"]} for r in aceitos for tag in r["tags"] or []))
    funil.salvar(pasta / "funil.csv")


# ---------- fluxo completo ----------

def _cota(api: GitHubAPI) -> str:
    return "?" if api.restante is None else str(api.restante)


def executar(
    api: GitHubAPI,
    faixas: Iterable[str],
    inicio: date,
    fim: date,
    limite: int,
    pasta_cache: str | Path,
    pasta_saida: str | Path,
    coletar_tags: bool = False,
) -> Funil:
    """Seleção -> Actions -> metadados -> releases (>= 5) -> runs (>= 50), até `limite` aceitos."""
    assinatura = {"inicio": str(inicio), "fim": str(fim), "coletar_tags": coletar_tags}
    candidatos = buscar_candidatos(api, faixas)
    log.info("%d candidatos; buscando %d repositórios na amostra", len(candidatos), limite)

    resultados: list[dict] = []
    aceitos: list[dict] = []
    for i, candidato in enumerate(candidatos, start=1):
        if len(aceitos) >= limite:
            break
        repo = candidato["full_name"]
        resultado = ler_marcador(pasta_cache, repo, assinatura)
        origem = "marcador"
        if resultado is None:
            origem = "api"
            log.info("repo %d/%d %s | amostra %d/%d | cota %s",
                     i, len(candidatos), repo, len(aceitos), limite, _cota(api))
            resultado = avaliar_repo(api, repo, inicio, fim, coletar_tags)
            gravar_marcador(pasta_cache, repo, assinatura, resultado)
        resultados.append(resultado)
        if resultado["aceito"]:
            aceitos.append(resultado)
        log.info("repo %d/%d %s -> %s (%s) | amostra %d/%d | cota %s",
                 i, len(candidatos), repo,
                 "aceito" if resultado["aceito"] else f"descartado: {resultado['motivo']}",
                 origem, len(aceitos), limite, _cota(api))

    if len(aceitos) < limite:
        log.warning("candidatos acabaram com %d de %d repositórios na amostra", len(aceitos), limite)
    funil = montar_funil(len(candidatos), resultados, limite)
    salvar_csvs(pasta_saida, aceitos, funil, coletar_tags)
    return funil

"""Coleta das releases, dos commits entre releases (RQ 01, RQ 02, CFR b) e das tags (RQ 07).

As releases são listadas inteiras, não só as da janela: a primeira release da janela precisa
da anterior, que pode estar fora dela, para o compare.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from urllib.parse import quote

from lab03.pipeline.api import GitHubAPI, RecursoAusente
from lab03.pipeline.runs import Dia, _dia

CAMPOS_RELEASE = ("tag_name", "published_at", "prerelease", "html_url")
POR_PAGINA = 100

log = logging.getLogger(__name__)


def _data(valor: str) -> datetime:
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def listar_releases(api: GitHubAPI, repo: str) -> list[dict]:
    """Todas as releases publicadas (sem drafts), da mais antiga para a mais nova."""
    releases = [
        {campo: r.get(campo) for campo in CAMPOS_RELEASE}
        for r in api.paginar(f"/repos/{repo}/releases")
        if not r.get("draft") and r.get("published_at")
    ]
    return sorted(releases, key=lambda r: _data(r["published_at"]))


def releases_na_janela(releases: list[dict], inicio: Dia, fim: Dia, com_pre: bool = False) -> list[dict]:
    """Releases publicadas entre `inicio` e `fim` (dias inteiros, UTC).

    Sem `com_pre` é a definição principal (funil e métricas); com ele, a variante C2 da RQ 07.
    """
    inicio, fim = _dia(inicio), _dia(fim)
    return [
        r for r in releases
        if inicio <= _data(r["published_at"]).date() <= fim and (com_pre or not r["prerelease"])
    ]


def release_anterior(releases: list[dict], release: dict) -> Optional[dict]:
    """Release não-pré-release imediatamente antes de `release`, mesmo fora da janela."""
    posicao = next(i for i, r in enumerate(releases) if r["tag_name"] == release["tag_name"])
    for candidata in reversed(releases[:posicao]):
        if not candidata["prerelease"]:
            return candidata
    return None


def _enxugar_commit(commit: dict) -> dict:
    return {
        "sha": commit["sha"],
        "data": commit["commit"]["author"]["date"],
        "mensagem": (commit["commit"]["message"] or "").split("\n", 1)[0],
    }


def commits_da_release(api: GitHubAPI, repo: str, tag_anterior: str, tag: str) -> list[dict]:
    """Commits em `tag` que não estão em `tag_anterior`.

    Sem `page`, o compare para em 250 commits; por isso pagina até juntar `total_commits`.
    Levanta `RecursoAusente` se uma das tags não existe mais.
    """
    caminho = f"/repos/{repo}/compare/{quote(tag_anterior, safe='')}...{quote(tag, safe='')}"
    commits: list[dict] = []
    pagina = 1
    while True:
        corpo = api.get(caminho, {"per_page": POR_PAGINA, "page": pagina})
        lote = corpo["commits"]
        commits.extend(_enxugar_commit(c) for c in lote)
        if not lote or len(commits) >= corpo["total_commits"]:
            return commits
        pagina += 1


def listar_tags(api: GitHubAPI, repo: str) -> list[dict]:
    return [{"nome": t["name"], "sha": t["commit"]["sha"]} for t in api.paginar(f"/repos/{repo}/tags")]


def data_da_tag(api: GitHubAPI, repo: str, sha: str) -> str:
    """Tag não tem data: vale a do commit apontado. Committer, e não author, porque é quando o
    commit chegou ao branch (um rebase mantém o author date antigo)."""
    return api.get(f"/repos/{repo}/commits/{sha}")["commit"]["committer"]["date"]


def _tags_com_data(api: GitHubAPI, repo: str) -> list[dict]:
    tags = []
    for tag in listar_tags(api, repo):
        try:
            tags.append({**tag, "data": data_da_tag(api, repo, tag["sha"])})
        except RecursoAusente:
            log.warning("%s: commit %s da tag %s não existe, ignorando", repo, tag["sha"], tag["nome"])
    return sorted(tags, key=lambda t: _data(t["data"]))


def coletar(
    api: GitHubAPI, repo: str, inicio: Dia, fim: Dia, com_pre: bool = False, coletar_tags: bool = False
) -> dict:
    """Releases da janela, cada uma com seus commits, mais as tags se `coletar_tags`.

    Cada release ganha `commits`, `sem_anterior` (primeira da história, fora do lead time) e
    `ignorada_compare_404` (tag apagada ou reescrita, FAQ do enunciado).
    """
    todas = listar_releases(api, repo)
    releases = []
    for release in releases_na_janela(todas, inicio, fim, com_pre):
        anterior = release_anterior(todas, release)
        item = {**release, "commits": [], "sem_anterior": anterior is None, "ignorada_compare_404": False}
        if anterior is not None:
            try:
                item["commits"] = commits_da_release(api, repo, anterior["tag_name"], release["tag_name"])
            except RecursoAusente:
                log.warning("%s: compare %s...%s deu 404, ignorando a release",
                            repo, anterior["tag_name"], release["tag_name"])
                item["ignorada_compare_404"] = True
        releases.append(item)
    return {
        "releases": releases,
        "ignoradas_compare_404": sum(r["ignorada_compare_404"] for r in releases),
        "tags": _tags_com_data(api, repo) if coletar_tags else None,
    }

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

# `body` (notas) é lido pela heurística de release corretiva (#96), mas não vai para o releases.csv
CAMPOS_RELEASE = ("tag_name", "published_at", "prerelease", "html_url", "body")
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


def release_anterior(releases: list[dict], release: dict, com_pre: bool = False) -> Optional[dict]:
    """Release imediatamente antes de `release`, mesmo fora da janela.

    Sem `com_pre` pula as pré-releases (definição principal). Com ele, na unidade
    "release + pré-release" da C2, a entrega anterior pode ser uma pré-release.
    """
    posicao = next(i for i, r in enumerate(releases) if r["tag_name"] == release["tag_name"])
    for candidata in reversed(releases[:posicao]):
        if com_pre or not candidata["prerelease"]:
            return candidata
    return None


def _primeira_linha(mensagem: Optional[str]) -> str:
    return (mensagem or "").split("\n", 1)[0]


def _enxugar_commit(commit: dict) -> dict:
    return {
        "sha": commit["sha"],
        "data": commit["commit"]["author"]["date"],
        "mensagem": _primeira_linha(commit["commit"]["message"]),
    }


def _compare_enxuto(corpo: dict) -> dict:
    """O que fica no cache de uma página do compare: só o que `_enxugar_commit` lê.

    A resposta inteira traz o diff de cada arquivo e os dados completos de autor e committer;
    num repo grande isso dá centenas de MB de cache. Aplicar duas vezes não muda nada.
    """
    return {
        "total_commits": corpo["total_commits"],
        "commits": [
            {"sha": c["sha"],
             "commit": {"author": {"date": c["commit"]["author"]["date"]},
                        "message": _primeira_linha(c["commit"]["message"])}}
            for c in corpo["commits"]
        ],
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
        corpo = api.get(caminho, {"per_page": POR_PAGINA, "page": pagina}, enxugar=_compare_enxuto)
        lote = corpo["commits"]
        commits.extend(_enxugar_commit(c) for c in lote)
        if not lote or len(commits) >= corpo["total_commits"]:
            return commits
        pagina += 1


# Tag leve aponta direto para o commit; tag anotada aponta para um objeto Tag, que aponta para o
# commit (ou, raramente, para outra Tag). Tag que aponta para árvore ou blob fica de fora.
_CONSULTA_TAGS = """
query($dono: String!, $nome: String!, $depois: String) {
  repository(owner: $dono, name: $nome) {
    refs(refPrefix: "refs/tags/", first: 100, after: $depois,
         orderBy: {field: TAG_COMMIT_DATE, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        target {
          __typename
          ... on Commit { oid committedDate }
          ... on Tag { target { __typename
            ... on Commit { oid committedDate }
            ... on Tag { target { __typename ... on Commit { oid committedDate } } } } }
        }
      }
    }
  }
}
"""


def _commit_da_tag(alvo: Optional[dict]) -> Optional[dict]:
    """Segue as tags anotadas até o commit."""
    while alvo is not None and alvo.get("__typename") == "Tag":
        alvo = alvo.get("target")
    if alvo is None or alvo.get("__typename") != "Commit":
        return None
    return alvo


def listar_tags(api: GitHubAPI, repo: str, desde: Optional[Dia] = None) -> list[dict]:
    """Tags com a data do commit apontado, da mais antiga para a mais nova.

    A data é a do committer (`committedDate`), não a do author: é quando o commit chegou ao branch,
    e um rebase mantém o author date antigo. A GraphQL devolve 100 tags por chamada já ordenadas
    da mais nova para a mais velha, então com `desde` a listagem para na primeira tag anterior a
    esse dia, que é a entrega anterior da primeira tag da janela.
    """
    dono, nome = repo.split("/")
    limite = _dia(desde) if desde is not None else None
    tags: list[dict] = []
    depois = None
    while True:
        dados = api.graphql(_CONSULTA_TAGS, {"dono": dono, "nome": nome, "depois": depois})
        refs = dados["repository"]["refs"]
        for ref in refs["nodes"]:
            commit = _commit_da_tag(ref["target"])
            if commit is None:
                continue
            tags.append({"nome": ref["name"], "sha": commit["oid"], "data": commit["committedDate"]})
        antes_do_limite = limite is not None and tags and _data(tags[-1]["data"]).date() < limite
        if antes_do_limite or not refs["pageInfo"]["hasNextPage"]:
            return sorted(tags, key=lambda t: (_data(t["data"]), t["nome"]))
        depois = refs["pageInfo"]["endCursor"]


def _uma_por_commit(tags: list[dict]) -> list[dict]:
    """Várias tags no mesmo commit (monorepo que marca cada pacote) são uma entrega só: fica a
    primeira pelo nome."""
    vistas, unicas = set(), []
    for tag in sorted(tags, key=lambda t: (_data(t["data"]), t["nome"])):
        if tag["sha"] not in vistas:
            vistas.add(tag["sha"])
            unicas.append(tag)
    return unicas


def entregas_por_tag(api: GitHubAPI, repo: str, inicio: Dia, fim: Dia) -> list[dict]:
    """Unidade de deploy "tag" da C3: cada tag da janela, com os commits desde a tag anterior.

    Sai no mesmo formato das releases (`tag_name`, `published_at`, `commits`, `sem_anterior`,
    `ignorada_compare_404`), para as funções de `lab03/metricas` lerem igual. Tag não tem notas, então
    `body` fica vazio. `published_at` é a data do commit apontado.
    """
    inicio, fim = _dia(inicio), _dia(fim)
    tags = _uma_por_commit(listar_tags(api, repo, desde=inicio))
    entregas = []
    for posicao, tag in enumerate(tags):
        if not inicio <= _data(tag["data"]).date() <= fim:
            continue
        anterior = tags[posicao - 1] if posicao > 0 else None
        item = {"tag_name": tag["nome"], "sha": tag["sha"], "published_at": tag["data"], "body": None,
                "commits": [], "sem_anterior": anterior is None, "ignorada_compare_404": False}
        if anterior is not None:
            try:
                item["commits"] = commits_da_release(api, repo, anterior["nome"], tag["nome"])
            except RecursoAusente:
                log.warning("%s: compare %s...%s deu 404, ignorando a tag", repo, anterior["nome"], tag["nome"])
                item["ignorada_compare_404"] = True
        entregas.append(item)
    return entregas


def coletar(
    api: GitHubAPI, repo: str, inicio: Dia, fim: Dia, com_pre: bool = False, coletar_tags: bool = False
) -> dict:
    """Releases da janela, cada uma com seus commits, mais as tags se `coletar_tags`.

    Com `com_pre` (C2), entram as pré-releases e a anterior de cada entrega pode ser uma delas.

    Cada release ganha `commits`, `sem_anterior` (primeira da história, fora do lead time) e
    `ignorada_compare_404` (tag apagada ou reescrita, FAQ do enunciado).
    """
    todas = listar_releases(api, repo)
    releases = []
    for release in releases_na_janela(todas, inicio, fim, com_pre):
        anterior = release_anterior(todas, release, com_pre)
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
        "tags": listar_tags(api, repo) if coletar_tags else None,
    }

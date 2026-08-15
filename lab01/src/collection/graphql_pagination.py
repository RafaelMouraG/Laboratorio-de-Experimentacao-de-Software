"""Paginação e retry compartilhados pelas consultas GraphQL de busca de repositórios.

Usado por collect_all_rqs.py e collect_sample_rq03_rq04.py, que paginam sobre
`search(type: REPOSITORY)`. As demais coletas (RQ01/RQ02, RQ05/RQ06) pedem uma
página só e não precisam disso.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import requests

GRAPHQL_URL = "https://api.github.com/graphql"

RETRYABLE_STATUS_CODES = (502, 503, 504)


def run_query(token: str, query: str, variables: dict) -> dict | None:
    """Executa a query. Devolve None quando a API recusa a página (502/503/504)."""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=30,
    )
    if response.status_code in RETRYABLE_STATUS_CODES:
        return None
    response.raise_for_status()
    payload = response.json()
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


def fetch_all_repos(
    token: str,
    query: str,
    total: int,
    page_size: int = 25,
    search_query: str = "stars:>1 sort:stars-desc",
) -> list[dict]:
    """Pagina `search(type: REPOSITORY)` até reunir `total` repositórios.

    A query precisa declarar `$searchQuery: String!`, `$pageSize: Int!` e
    `$after: String`, e pedir `rateLimit { remaining resetAt }` e
    `search(...) { pageInfo { hasNextPage endCursor } nodes { ... } }`.

    Reduz o tamanho da página pela metade quando a API recusa (502/503/504) e
    pausa a execução quando o rate limit está perto de acabar.
    """
    all_nodes: list[dict] = []
    cursor: str | None = None
    has_next_page = True

    while len(all_nodes) < total and has_next_page:
        tamanho = min(page_size, total - len(all_nodes))

        data = None
        while data is None:
            variables = {"searchQuery": search_query, "pageSize": tamanho, "after": cursor}
            print(f"Buscando página de {tamanho} (faltam {total - len(all_nodes)} repositórios)...")
            data = run_query(token, query, variables)
            if data is not None:
                break
            if tamanho == 1:
                raise RuntimeError(f"a API recusou a consulta de 1 repositório (cursor {cursor})")
            tamanho = max(1, tamanho // 2)
            print(f"  página recusada pela API, reduzindo para {tamanho} repositórios")
            time.sleep(2)

        search = data["search"]
        all_nodes.extend(search["nodes"])

        rate_limit = data["rateLimit"]
        print(
            f"{len(all_nodes)}/{total} repositórios | "
            f"rate limit: {rate_limit['remaining']} restantes (reset {rate_limit['resetAt']})"
        )

        page_info = search["pageInfo"]
        has_next_page = page_info["hasNextPage"]
        cursor = page_info["endCursor"]

        if rate_limit["remaining"] < 5 and has_next_page:
            reset_time = datetime.fromisoformat(rate_limit["resetAt"].replace("Z", "+00:00"))
            sleep_seconds = (reset_time - datetime.now(timezone.utc)).total_seconds() + 10
            if sleep_seconds > 0:
                print(f"Rate limit próximo do fim. Pausando por {sleep_seconds:.0f} segundos...")
                time.sleep(sleep_seconds)

    return all_nodes

"""Exporta o estado atual do GitHub Projects (Kanban) do grupo para CSV.

O GitHub Projects não guarda histórico de mudança de coluna consultável via API: só o estado
atual de cada cartão. Rodando este script ao fim de cada sprint, a série de snapshots acumulada
passa a fazer esse papel e vira a base de dados dos Labs 04 e 05.
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

GRAPHQL_URL = "https://api.github.com/graphql"

PAGE_SIZE = 50

STATUS_SEM_COLUNA = "Sem Status"

# Ordem das colunas no board, usada para ordenar o CSV. Status fora desta lista vai para o fim.
ORDEM_STATUS = ["Backlog", "To Do", "Doing", "Review", "Done", STATUS_SEM_COLUNA]

QUERY = """
query ($login: String!, $number: Int!, $first: Int!, $after: String) {
  rateLimit {
    remaining
    resetAt
  }
  user(login: $login) {
    projectV2(number: $number) {
      title
      url
      items(first: $first, after: $after) {
        totalCount
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          type
          fieldValueByName(name: "Status") {
            ... on ProjectV2ItemFieldSingleSelectValue {
              name
            }
          }
          content {
            ... on Issue {
              number
              title
              url
              state
              assignees(first: 5) {
                nodes {
                  login
                }
              }
            }
            ... on DraftIssue {
              title
            }
            ... on PullRequest {
              number
              title
              url
              state
            }
          }
        }
      }
    }
  }
}
"""


def fetch_page(token: str, login: str, number: int, first: int, after: str = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    variables = {
        "login": login,
        "number": number,
        "first": first,
        "after": after,
    }
    response = requests.post(
        GRAPHQL_URL,
        json={"query": QUERY, "variables": variables},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if "errors" in payload:
        raise RuntimeError(payload["errors"])

    return payload["data"]


def fetch_all_items(token: str, login: str, number: int) -> tuple[dict, list[dict]]:
    """Percorre todas as páginas de itens do project. Devolve (dados do project, itens)."""
    all_nodes = []
    has_next_page = True
    end_cursor = None
    project = None
    first = PAGE_SIZE

    while has_next_page:
        success = False
        while not success:
            try:
                data = fetch_page(token, login, number, first, end_cursor)
                success = True
            except requests.exceptions.HTTPError as e:
                if e.response.status_code in (502, 504) and first > 1:
                    first = max(1, first // 2)
                    print(f"A API retornou erro {e.response.status_code}. Reduzindo lote para {first} e tentando novamente...")
                    time.sleep(2)
                else:
                    raise

        user = data["user"]
        if not user or not user["projectV2"]:
            sys.exit(f"Project número {number} não encontrado para o usuário {login}.")

        project = user["projectV2"]
        items = project["items"]
        all_nodes.extend(items["nodes"])

        page_info = items["pageInfo"]
        has_next_page = page_info["hasNextPage"]
        end_cursor = page_info["endCursor"]

        print(f"Lidos {len(all_nodes)} de {items['totalCount']} itens do board...")

        rate_limit = data["rateLimit"]
        if rate_limit["remaining"] < 5 and has_next_page:
            reset_time = datetime.fromisoformat(rate_limit["resetAt"].replace("Z", "+00:00"))
            sleep_seconds = (reset_time - datetime.now(timezone.utc)).total_seconds() + 10
            if sleep_seconds > 0:
                print(f"Rate limit próximo do fim. Pausando por {sleep_seconds:.0f} segundos...")
                time.sleep(sleep_seconds)

    return project, all_nodes


def to_rows(nodes: list[dict], sprint: str) -> list[dict]:
    snapshot_date = datetime.now(timezone.utc).date().isoformat()
    rows = []

    for item in nodes:
        content = item.get("content")
        if not content:
            # Issue em repositório que o token não enxerga.
            continue

        status_field = item.get("fieldValueByName")
        status = status_field["name"] if status_field else STATUS_SEM_COLUNA

        # Draft issue não tem número, URL nem estado; ainda assim entra no CSV para não
        # perder o cartão do board.
        assignees = content.get("assignees")
        logins = [node["login"] for node in assignees["nodes"]] if assignees else []

        rows.append(
            {
                "snapshot_date": snapshot_date,
                "sprint": sprint,
                "issue": content.get("number", ""),
                "titulo": content["title"],
                "status": status,
                "assignee": ";".join(logins),
                "state": content.get("state", ""),
                "url": content.get("url", ""),
            }
        )

    def ordenar(row: dict):
        status = row["status"]
        posicao = ORDEM_STATUS.index(status) if status in ORDEM_STATUS else len(ORDEM_STATUS)
        return (posicao, status, row["issue"] if row["issue"] != "" else 0)

    rows.sort(key=ordenar)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta o snapshot do Kanban do grupo para CSV.")
    parser.add_argument("--login", default="RafaelMouraG", help="dono do GitHub Projects")
    parser.add_argument("--number", type=int, default=6, help="número do ProjectV2")
    parser.add_argument("--sprint", default="S01", help="rótulo da sprint gravado no CSV")
    parser.add_argument("--out", default="kanban/snapshots/snapshot_sprint_01.csv")
    args = parser.parse_args()

    load_dotenv()
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN não definido. Crie um .env na raiz do projeto com o seu token.")

    print(f"Lendo o project #{args.number} de {args.login}...")
    project, nodes = fetch_all_items(token, args.login, args.number)
    rows = to_rows(nodes, args.sprint)

    if not rows:
        print("\nNenhum item encontrado no board.")
        return

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nProject: {project['title']} ({project['url']})")
    print(f"Sucesso! Salvos {len(rows)} itens em {args.out}")

    print("\nDistribuição por coluna:")
    for status in ORDEM_STATUS:
        total = sum(1 for row in rows if row["status"] == status)
        if total:
            print(f"  {status}: {total}")

    fora_da_ordem = sorted({row["status"] for row in rows} - set(ORDEM_STATUS))
    for status in fora_da_ordem:
        total = sum(1 for row in rows if row["status"] == status)
        print(f"  {status}: {total} (coluna nova, acrescente em ORDEM_STATUS)")


if __name__ == "__main__":
    main()

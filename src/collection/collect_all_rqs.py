"""Script unificado para coletar RQs 01 a 06 com suporte a paginação."""

import argparse
import csv
import os
import sys
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

GRAPHQL_URL = "https://api.github.com/graphql"

QUERY = """
query ($searchQuery: String!, $first: Int!, $after: String) {
  rateLimit {
    remaining
    resetAt
  }
  search(query: $searchQuery, type: REPOSITORY, first: $first, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      ... on Repository {
        nameWithOwner
        stargazerCount
        createdAt
        updatedAt
        primaryLanguage {
          name
        }
        releases {
          totalCount
        }
        pullRequests(states: MERGED) {
          totalCount
        }
        issues {
          totalCount
        }
        closedIssues: issues(states: CLOSED) {
          totalCount
        }
      }
    }
  }
}
"""


def fetch_page(token: str, first: int, after: str = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    variables = {
        "searchQuery": "stars:>1 sort:stars-desc",
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


def fetch_all_repos(token: str, total_requested: int) -> list[dict]:
    all_nodes = []
    has_next_page = True
    end_cursor = None

    while len(all_nodes) < total_requested and has_next_page:
        remaining_to_fetch = total_requested - len(all_nodes)
        first = min(25, remaining_to_fetch)

        success = False
        while not success:
            print(f"Buscando página de {first} (faltam {remaining_to_fetch} repositórios)...")
            try:
                data = fetch_page(token, first, end_cursor)
                success = True
            except requests.exceptions.HTTPError as e:
                if e.response.status_code in (502, 504) and first > 1:
                    first = max(1, first // 2)
                    print(f"A API retornou erro {e.response.status_code}. Reduzindo lote para {first} e tentando novamente...")
                    time.sleep(2)
                else:
                    raise

        rate_limit = data["rateLimit"]
        search_data = data["search"]

        all_nodes.extend(search_data["nodes"])
        
        page_info = search_data["pageInfo"]
        has_next_page = page_info["hasNextPage"]
        end_cursor = page_info["endCursor"]

        print(f"Rate limit: {rate_limit['remaining']} restantes (reset {rate_limit['resetAt']})")

        if rate_limit["remaining"] < 5 and has_next_page:
            reset_time = datetime.fromisoformat(rate_limit["resetAt"].replace("Z", "+00:00"))
            sleep_seconds = (reset_time - datetime.now(timezone.utc)).total_seconds() + 10
            if sleep_seconds > 0:
                print(f"Rate limit próximo do fim. Pausando por {sleep_seconds:.0f} segundos...")
                time.sleep(sleep_seconds)

    return all_nodes


def to_rows(nodes: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc)
    rows = []
    for repo in nodes:
        if not repo:
            continue
            
        created_at = datetime.fromisoformat(repo["createdAt"].replace("Z", "+00:00"))
        age_years = (now - created_at).days / 365.25

        updated_at = datetime.fromisoformat(repo["updatedAt"].replace("Z", "+00:00"))
        days_since_update = (now - updated_at).days

        primary_language = repo["primaryLanguage"]["name"] if repo.get("primaryLanguage") else "N/A"
        
        total_issues = repo["issues"]["totalCount"]
        closed_issues = repo["closedIssues"]["totalCount"]
        closed_issues_ratio = closed_issues / total_issues if total_issues > 0 else 0.0

        rows.append(
            {
                "repo": repo["nameWithOwner"],
                "stars": repo["stargazerCount"],
                "created_at": repo["createdAt"],
                "age_years": round(age_years, 2), # RQ01
                "merged_pull_requests": repo["pullRequests"]["totalCount"], # RQ02
                "total_releases": repo["releases"]["totalCount"], # RQ03
                "updated_at": repo["updatedAt"],
                "days_since_update": days_since_update, # RQ04
                "primary_language": primary_language, # RQ05
                "total_issues": total_issues,
                "closed_issues": closed_issues,
                "closed_issues_ratio": round(closed_issues_ratio, 4), # RQ06
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100, help="quantidade total de repositórios a buscar")
    parser.add_argument("--out", default="data/sprint_s01/all_rqs.csv")
    args = parser.parse_args()

    load_dotenv()
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN não definido. Copie .env.example para .env e preencha o token.")

    print(f"Iniciando coleta de {args.n} repositórios...")
    nodes = fetch_all_repos(token, args.n)
    rows = to_rows(nodes)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    
    if rows:
        keys = rows[0].keys()
        with open(args.out, 'w', newline='', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(rows)

        print(f"\nSucesso! Salvos {len(rows)} repositórios em {args.out}")
    else:
        print("\nNenhum dado encontrado.")


if __name__ == "__main__":
    main()

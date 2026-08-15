"""Script unificado para coletar RQs 01 a 06 com suporte a paginação."""

import argparse
import csv
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from graphql_pagination import fetch_all_repos

RELEASES_CAP = 1000

QUERY = """
query ($searchQuery: String!, $pageSize: Int!, $after: String) {
  rateLimit {
    remaining
    resetAt
  }
  search(query: $searchQuery, type: REPOSITORY, first: $pageSize, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      ... on Repository {
        nameWithOwner
        stargazerCount
        createdAt
        pushedAt
        updatedAt
        primaryLanguage {
          name
        }
        releases(orderBy: {field: CREATED_AT, direction: DESC}) {
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


def to_rows(nodes: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc)
    rows = []
    for repo in nodes:
        if not repo:
            continue
            
        created_at = datetime.fromisoformat(repo["createdAt"].replace("Z", "+00:00"))
        age_years = (now - created_at).days / 365.25

        # RQ04 usa pushedAt (último commit). updatedAt muda com star/label e infla a métrica.
        pushed_at = datetime.fromisoformat(repo["pushedAt"].replace("Z", "+00:00"))
        updated_at = datetime.fromisoformat(repo["updatedAt"].replace("Z", "+00:00"))
        days_since_last_push = (now - pushed_at).total_seconds() / 86400
        days_since_last_update = (now - updated_at).total_seconds() / 86400

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
                "releases": repo["releases"]["totalCount"], # RQ03
                "pushed_at": repo["pushedAt"],
                "updated_at": repo["updatedAt"],
                "days_since_last_push": round(days_since_last_push, 2), # RQ04
                "days_since_last_update": round(days_since_last_update, 2),
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
    parser.add_argument("--out", default="lab01/data/sprint_s01/all_rqs.csv")
    args = parser.parse_args()

    load_dotenv()
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN não definido. Copie .env.example para .env e preencha o token.")

    print(f"Iniciando coleta de {args.n} repositórios...")
    nodes = fetch_all_repos(token, QUERY, args.n)
    rows = to_rows(nodes)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    
    if rows:
        keys = rows[0].keys()
        with open(args.out, 'w', newline='', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(rows)

        print(f"\nSucesso! Salvos {len(rows)} repositórios em {args.out}")

        truncados = [row["repo"] for row in rows if row["releases"] == RELEASES_CAP]
        if truncados:
            print(
                f"  atenção: {len(truncados)} repositório(s) com exatamente {RELEASES_CAP} releases "
                f"({', '.join(truncados)}). Confirme que o orderBy continua na query de releases: "
                "sem ele a API trunca a contagem nesse valor."
            )
    else:
        print("\nNenhum dado encontrado.")


if __name__ == "__main__":
    main()

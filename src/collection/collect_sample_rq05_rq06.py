"""Validação individual (RQ05 + RQ06)"""

import argparse
import csv
import os
import sys

import requests
from dotenv import load_dotenv

GRAPHQL_URL = "https://api.github.com/graphql"

QUERY = """
query ($searchQuery: String!, $n: Int!) {
  rateLimit {
    remaining
    resetAt
  }
  search(query: $searchQuery, type: REPOSITORY, first: $n) {
    nodes {
      ... on Repository {
        nameWithOwner
        stargazerCount
        primaryLanguage {
          name
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


def fetch_sample(token: str, n: int) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"}
    variables = {"searchQuery": "stars:>1 sort:stars-desc", "n": n}
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

    rate_limit = payload["data"]["rateLimit"]
    print(f"Rate limit: {rate_limit['remaining']} restantes (reset {rate_limit['resetAt']})")

    return payload["data"]["search"]["nodes"]


def to_rows(nodes: list[dict]) -> list[dict]:
    rows = []
    for repo in nodes:
        primary_language = repo["primaryLanguage"]["name"] if repo.get("primaryLanguage") else "N/A"
        total_issues = repo["issues"]["totalCount"]
        closed_issues = repo["closedIssues"]["totalCount"]
        
        ratio = 0.0
        if total_issues > 0:
            ratio = closed_issues / total_issues

        rows.append(
            {
                "repo": repo["nameWithOwner"],
                "stars": repo["stargazerCount"],
                "primary_language": primary_language,
                "total_issues": total_issues,
                "closed_issues": closed_issues,
                "closed_issues_ratio": round(ratio, 4),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=10, help="quantidade de repositórios a buscar")
    parser.add_argument("--out", default="data/amostra/rq05_rq06.csv")
    args = parser.parse_args()

    load_dotenv()
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN não definido. Copie .env.example para .env e preencha o token.")

    nodes = fetch_sample(token, args.n)
    rows = to_rows(nodes)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    
    if rows:
        keys = rows[0].keys()
        with open(args.out, 'w', newline='', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(rows)

        print(f"Salvos {len(rows)} repositórios em {args.out}")


if __name__ == "__main__":
    main()

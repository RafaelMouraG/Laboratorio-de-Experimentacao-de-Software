"""Validação individual (RQ01 + RQ02)"""

import argparse
import os
import sys
from datetime import datetime, timezone

import pandas as pd
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
        createdAt
        stargazerCount
        pullRequests(states: MERGED) {
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
    now = datetime.now(timezone.utc)
    rows = []
    for repo in nodes:
        created_at = datetime.fromisoformat(repo["createdAt"].replace("Z", "+00:00"))
        age_years = (now - created_at).days / 365.25
        rows.append(
            {
                "repo": repo["nameWithOwner"],
                "stars": repo["stargazerCount"],
                "created_at": repo["createdAt"],
                "age_years": round(age_years, 2),
                "merged_pull_requests": repo["pullRequests"]["totalCount"],
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=10, help="quantidade de repositórios a buscar")
    parser.add_argument("--out", default="lab01/data/amostra/rq01_rq02_10.csv")
    args = parser.parse_args()

    load_dotenv()
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN não definido. Copie .env.example para .env e preencha o token.")

    nodes = fetch_sample(token, args.n)
    rows = to_rows(nodes)

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df.to_csv(args.out, index=False)

    print(df.to_string(index=False))
    print(f"\nSalvo em {args.out}")
    print("Valide manualmente 2-3 linhas contra github.com/<repo> (data de criação e aba Pull requests > Closed, filtrando merged).")


if __name__ == "__main__":
    main()

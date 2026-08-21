"""Validação individual (RQ03 + RQ04)"""

import argparse
import os
import sys
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv

from graphql_pagination import fetch_all_repos

PAGE_SIZE = 25
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
        primaryLanguage {
          name
        }
        releases(orderBy: {field: CREATED_AT, direction: DESC}) {
          totalCount
        }
        pushedAt
        updatedAt
      }
    }
  }
}
"""


def fetch_sample(token: str, n: int, page_size: int = PAGE_SIZE) -> list[dict]:
    return fetch_all_repos(token, QUERY, n, page_size=page_size)


def to_rows(nodes: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc)
    rows = []
    for repo in nodes:
        pushed_at = datetime.fromisoformat(repo["pushedAt"].replace("Z", "+00:00"))
        updated_at = datetime.fromisoformat(repo["updatedAt"].replace("Z", "+00:00"))
        days_since_last_push = (now - pushed_at).total_seconds() / 86400
        days_since_last_update = (now - updated_at).total_seconds() / 86400
        primary_language = repo["primaryLanguage"]["name"] if repo.get("primaryLanguage") else "N/A"
        releases = repo["releases"]["totalCount"]

        rows.append(
            {
                "repo": repo["nameWithOwner"],
                "stars": repo["stargazerCount"],
                "primary_language": primary_language,
                "releases": releases,
                "pushed_at": repo["pushedAt"],
                "updated_at": repo["updatedAt"],
                "days_since_last_push": round(days_since_last_push, 2),
                "days_since_last_update": round(days_since_last_update, 2),
            }
        )
    return rows


def print_pushed_vs_updated(df: pd.DataFrame, gap_dias: int = 180) -> None:
    """Verifica se pushedAt e updatedAt levariam a respostas diferentes na RQ04."""
    gap = df["days_since_last_update"] - df["days_since_last_push"]
    parados = df[gap.abs() > gap_dias]

    print("\nRQ04 - pushedAt vs updatedAt:")
    print(f"  mediana de dias por pushedAt (métrica usada): {df['days_since_last_push'].median()}")
    print(f"  mediana de dias por updatedAt (descartado):   {df['days_since_last_update'].median()}")
    print(f"  repos com divergência > {gap_dias} dias: {len(parados)} de {len(df)}")

    if not parados.empty:
        print("  maiores divergências:")
        colunas = ["repo", "days_since_last_push", "days_since_last_update"]
        print(parados.assign(gap=gap).sort_values("gap", ascending=False)[colunas].head().to_string(index=False))


def print_by_language(df: pd.DataFrame) -> None:
    """RQ07: RQ03 e RQ04 agrupados por linguagem primária."""
    grouped = (
        df.groupby("primary_language")
        .agg(
            repos=("repo", "count"),
            mediana_releases=("releases", "median"),
            mediana_dias_sem_push=("days_since_last_push", "median"),
        )
        .sort_values("repos", ascending=False)
    )
    print("\nPor linguagem (RQ07):")
    print(grouped.to_string())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=10, help="quantidade de repositórios a buscar")
    parser.add_argument("--out", default="lab01/data/amostra/rq03_rq04.csv")
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
    print(f"\nMediana de releases: {df['releases'].median()}")
    truncados = df.loc[df["releases"] == RELEASES_CAP, "repo"]
    if not truncados.empty:
        print(
            f"  atenção: {len(truncados)} repositório(s) com exatamente {RELEASES_CAP} releases "
            f"({', '.join(truncados)}). Confirme que o orderBy continua na query de releases: "
            "sem ele a API trunca a contagem nesse valor."
        )
    print(f"Mediana de dias desde o último push: {df['days_since_last_push'].median()}")
    print_pushed_vs_updated(df)
    print_by_language(df)

    print(f"\nSalvo em {args.out}")
    print("Valide manualmente 2-3 linhas contra github.com/<repo> (aba Releases e data do último commit).")


if __name__ == "__main__":
    main()

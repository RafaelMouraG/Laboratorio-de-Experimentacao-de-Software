"""RQ07: RQ02, RQ03 e RQ04 divididas por linguagem primária (RQ05)"""

import argparse
import os
import sys

import pandas as pd

TOP_LANGUAGES = [
    "Python",
    "JavaScript",
    "TypeScript",
    "Java",
    "C#",
    "C++",
    "PHP",
    "Shell",
    "C",
    "Go",
]

SEM_LINGUAGEM = "N/A"

GRUPO_TOP = "top-10 Octoverse"
GRUPO_DEMAIS = "demais linguagens"
GRUPO_NENHUMA = "sem linguagem primária"


def carregar(caminho: str, colunas: list[str]) -> pd.DataFrame:
    if not os.path.exists(caminho):
        sys.exit(f"{caminho} não encontrado. Rode antes os scripts de coleta das RQ01-RQ06.")

    df = pd.read_csv(caminho, keep_default_na=False)
    faltando = [coluna for coluna in colunas if coluna not in df.columns]
    if faltando:
        sys.exit(f"{caminho}: colunas ausentes {faltando}")
    return df[colunas]


def checar_linguagem(rq03_rq04: str, linguagens: pd.DataFrame) -> None:
    outra = carregar(rq03_rq04, ["repo", "primary_language"])
    comparacao = linguagens.merge(outra, on="repo", suffixes=("_rq05", "_rq03"))
    divergentes = comparacao[
        comparacao["primary_language_rq05"] != comparacao["primary_language_rq03"]
    ]
    if not divergentes.empty:
        print(
            f"atenção: {len(divergentes)} repositório(s) com linguagem diferente entre as coletas "
            "(vale usar a do CSV da RQ05, que é a fonte da métrica):"
        )
        print(divergentes.to_string(index=False))


def juntar(rq01_rq02: str, rq03_rq04: str, rq05_rq06: str) -> pd.DataFrame:
    prs = carregar(rq01_rq02, ["repo", "merged_pull_requests"])
    releases = carregar(rq03_rq04, ["repo", "releases", "days_since_last_push"])
    linguagens = carregar(rq05_rq06, ["repo", "primary_language"])

    checar_linguagem(rq03_rq04, linguagens)

    df = linguagens.merge(prs, on="repo", how="inner").merge(releases, on="repo", how="inner")

    entrada = max(len(prs), len(releases), len(linguagens))
    if len(df) < entrada:
        print(
            f"atenção: {entrada - len(df)} repositório(s) ficaram de fora do cruzamento. "
            "Os três CSVs precisam ser da mesma coleta (mesmos repositórios)."
        )

    return df.assign(grupo=df["primary_language"].map(classificar))


def classificar(linguagem: str) -> str:
    if linguagem == SEM_LINGUAGEM:
        return GRUPO_NENHUMA
    return GRUPO_TOP if linguagem in TOP_LANGUAGES else GRUPO_DEMAIS


def agregar(df: pd.DataFrame, chave: str) -> pd.DataFrame:
    return df.groupby(chave).agg(
        repos=("repo", "count"),
        mediana_prs_aceitas=("merged_pull_requests", "median"),
        mediana_releases=("releases", "median"),
        mediana_dias_sem_push=("days_since_last_push", "median"),
    )


def por_linguagem(df: pd.DataFrame) -> pd.DataFrame:
    tabela = agregar(df, "primary_language")
    tabela.insert(0, "grupo", [classificar(linguagem) for linguagem in tabela.index])
    return tabela.sort_values(["repos", "mediana_prs_aceitas"], ascending=False)


def por_grupo(df: pd.DataFrame) -> pd.DataFrame:
    ordem = [GRUPO_TOP, GRUPO_DEMAIS, GRUPO_NENHUMA]
    tabela = agregar(df, "grupo")
    return tabela.reindex([grupo for grupo in ordem if grupo in tabela.index])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rq01-rq02", default="data/sprint_s01/rq01_rq02.csv")
    parser.add_argument("--rq03-rq04", default="data/sprint_s01/rq03_rq04_100.csv")
    parser.add_argument("--rq05-rq06", default="data/sprint_s01/rq05_rq06_100.csv")
    parser.add_argument("--out", default="data/sprint_s01/rq07_por_linguagem.csv")
    parser.add_argument("--out-grupos", default="data/sprint_s01/rq07_top_vs_demais.csv")
    args = parser.parse_args()

    df = juntar(args.rq01_rq02, args.rq03_rq04, args.rq05_rq06)
    print(f"{len(df)} repositórios cruzados, {df['primary_language'].nunique()} linguagens distintas")
    print(f"Linguagens mais populares (Octoverse 2024): {', '.join(TOP_LANGUAGES)}")

    tabela_linguagem = por_linguagem(df)
    tabela_grupo = por_grupo(df)

    print("\nRQ07 - medianas por linguagem primária:")
    print(tabela_linguagem.to_string())

    print("\nRQ07 - linguagens mais populares vs. demais:")
    print(tabela_grupo.to_string())

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    tabela_linguagem.to_csv(args.out)
    tabela_grupo.to_csv(args.out_grupos)
    print(f"\nSalvo em {args.out} e {args.out_grupos}")
    print(
        "Lembre que a mediana de linguagens com poucos repositórios (coluna repos) diz pouco: "
        "leia a tabela por grupo para responder a RQ07."
    )


if __name__ == "__main__":
    main()

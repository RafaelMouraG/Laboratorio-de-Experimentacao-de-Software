"""Extra: idade (RQ01) explica o número de estrelas?"""

import argparse
import os
import sys

import pandas as pd

COLUNAS = ["repo", "stars", "age_years", "primary_language"]

FAIXAS = [0, 1, 3, 5, 10, 100]
ROTULOS = ["menos de 1 ano", "1 a 3 anos", "3 a 5 anos", "5 a 10 anos", "mais de 10 anos"]


def carregar(caminho: str) -> pd.DataFrame:
    if not os.path.exists(caminho):
        sys.exit(f"{caminho} não encontrado. Rode antes lab01/src/collection/collect_all_rqs.py.")

    df = pd.read_csv(caminho, keep_default_na=False)
    faltando = [coluna for coluna in COLUNAS if coluna not in df.columns]
    if faltando:
        sys.exit(f"{caminho}: colunas ausentes {faltando}")
    return df[COLUNAS]


def correlacoes(df: pd.DataFrame) -> pd.DataFrame:
    linhas = [
        {
            "metodo": "pearson (valores)",
            "correlacao": round(df["age_years"].corr(df["stars"]), 3),
        },
        {
            "metodo": "spearman (postos)",
            "correlacao": round(df["age_years"].rank().corr(df["stars"].rank()), 3),
        },
    ]
    return pd.DataFrame(linhas)


def por_faixa(df: pd.DataFrame) -> pd.DataFrame:
    faixa = pd.cut(df["age_years"], bins=FAIXAS, labels=ROTULOS, right=False)
    tabela = df.groupby(faixa, observed=False).agg(
        repos=("repo", "count"),
        mediana_stars=("stars", "median"),
        max_stars=("stars", "max"),
    )
    return tabela[tabela["repos"] > 0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", default="lab01/data/sprint_s01/all_rqs.csv")
    parser.add_argument("--out", default="lab01/data/sprint_s01/extra_idade_por_faixa.csv")
    parser.add_argument("--out-jovens", default="lab01/data/sprint_s01/extra_repos_jovens.csv")
    parser.add_argument("--listar", type=int, default=10)
    args = parser.parse_args()

    df = carregar(args.entrada)
    jovens = df.nsmallest(args.listar, "age_years").sort_values("stars", ascending=False)

    print(f"{len(df)} repositórios | idade mediana de {df['age_years'].median()} anos")

    tabela_correlacao = correlacoes(df)
    print("\nCorrelação entre idade e estrelas:")
    print(tabela_correlacao.to_string(index=False))

    tabela_faixa = por_faixa(df)
    print("\nEstrelas por faixa etária:")
    print(tabela_faixa.to_string())

    print(f"\nOs {args.listar} repositórios mais jovens da amostra:")
    print(jovens.to_string(index=False))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    tabela_faixa.to_csv(args.out)
    jovens.to_csv(args.out_jovens, index=False)
    print(f"\nSalvo em {args.out} e {args.out_jovens}")


if __name__ == "__main__":
    main()

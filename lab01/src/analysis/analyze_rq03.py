"""RQ03: releases por ano e recorte dos repositórios sem release"""

import argparse
import os
import sys

import pandas as pd

METRICAS = ["releases", "releases_por_ano"]


def carregar(caminho: str, colunas: list[str]) -> pd.DataFrame:
    if not os.path.exists(caminho):
        sys.exit(f"{caminho} não encontrado. Rode antes os scripts de coleta das RQ01-RQ06.")

    df = pd.read_csv(caminho, keep_default_na=False)
    faltando = [coluna for coluna in colunas if coluna not in df.columns]
    if faltando:
        sys.exit(f"{caminho}: colunas ausentes {faltando}")
    return df[colunas]


def juntar(entrada: str) -> pd.DataFrame:
    df = carregar(entrada, ["repo", "stars", "primary_language", "releases", "age_years"])

    return df.assign(
        releases_por_ano=(df["releases"] / df["age_years"]).round(2),
        sem_release=df["releases"] == 0,
    )


def resumo(df: pd.DataFrame) -> pd.DataFrame:
    recortes = [
        ("todos os repositórios", df),
        ("apenas com release", df[~df["sem_release"]]),
    ]
    linhas = []
    for metrica in METRICAS:
        for rotulo, recorte in recortes:
            serie = recorte[metrica]
            linhas.append(
                {
                    "metrica": metrica,
                    "recorte": rotulo,
                    "repos": len(recorte),
                    "mediana": round(serie.median(), 2),
                    "q1": round(serie.quantile(0.25), 2),
                    "q3": round(serie.quantile(0.75), 2),
                    "media": round(serie.mean(), 2),
                }
            )
    return pd.DataFrame(linhas)


def sem_release_por_linguagem(df: pd.DataFrame) -> pd.DataFrame:
    tabela = df.groupby("primary_language").agg(
        repos=("repo", "count"),
        sem_release=("sem_release", "sum"),
    )
    tabela = tabela.assign(
        percentual_sem_release=(100 * tabela["sem_release"] / tabela["repos"]).round(1)
    )
    return tabela[tabela["sem_release"] > 0].sort_values(
        ["sem_release", "repos"], ascending=False
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", default="lab01/data/sprint_s01/all_rqs.csv")
    parser.add_argument("--out", default="lab01/data/sprint_s01/rq03_releases_por_ano.csv")
    parser.add_argument("--out-resumo", default="lab01/data/sprint_s01/rq03_resumo.csv")
    parser.add_argument("--listar", type=int, default=15)
    args = parser.parse_args()

    df = juntar(args.entrada)
    sem_release = df[df["sem_release"]]
    print(
        f"{len(df)} repositórios | {len(sem_release)} sem nenhuma release "
        f"({round(100 * len(sem_release) / len(df), 1)}%)"
    )

    tabela_resumo = resumo(df)
    print("\nRQ03 - mediana com e sem os repositórios sem release:")
    print(tabela_resumo.to_string(index=False))

    print("\nRQ03 - repositórios sem release, por linguagem:")
    print(sem_release_por_linguagem(df).to_string())

    print(f"\nRQ03 - {args.listar} repositórios sem release com mais estrelas:")
    colunas = ["repo", "primary_language", "stars", "age_years"]
    print(sem_release.nlargest(args.listar, "stars")[colunas].to_string(index=False))

    print("\nRQ03 - maiores cadências (releases por ano):")
    colunas = ["repo", "primary_language", "age_years", "releases", "releases_por_ano"]
    print(df.nlargest(10, "releases_por_ano")[colunas].to_string(index=False))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df.to_csv(args.out, index=False)
    tabela_resumo.to_csv(args.out_resumo, index=False)
    print(f"\nSalvo em {args.out} e {args.out_resumo}")
    print(
        "A lista completa dos repositórios sem release sai filtrando a coluna sem_release do "
        f"{args.out}; a classificação do motivo (não é software / versiona por tag / distribui por "
        "registry externo) é manual e vai no relatório."
    )


if __name__ == "__main__":
    main()

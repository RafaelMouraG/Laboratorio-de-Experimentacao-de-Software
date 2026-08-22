"""RQ01: sistemas populares são maduros/antigos? — histograma e faixas etárias de age_years."""

import argparse

import matplotlib.pyplot as plt
import pandas as pd

from viz_common import carregar_dados, marcar_mediana, salvar, setup_estilo

FAIXAS = [0, 1, 3, 5, 10, 100]
ROTULOS = ["< 1 ano", "1-3 anos", "3-5 anos", "5-10 anos", "> 10 anos"]


def resumo(df) -> dict:
    serie = df["age_years"]
    return {
        "repos": len(serie),
        "mediana": round(serie.median(), 2),
        "q1": round(serie.quantile(0.25), 2),
        "q3": round(serie.quantile(0.75), 2),
        "min": round(serie.min(), 2),
        "max": round(serie.max(), 2),
    }


def grafico_histograma(df, nome: str) -> str:
    fig, ax = plt.subplots()
    ax.hist(df["age_years"], bins=30)
    ax.set_title("RQ01 - Distribuição da idade dos repositórios")
    ax.set_xlabel("idade (anos)")
    ax.set_ylabel("repositórios")
    mediana = round(df["age_years"].median(), 2)
    marcar_mediana(ax, mediana, rotulo=f"mediana = {mediana}")
    return salvar(fig, nome)


def grafico_faixas(df, nome: str) -> str:
    faixa = df.assign(faixa=pd.cut(df["age_years"], bins=FAIXAS, labels=ROTULOS, right=False))
    contagem = faixa["faixa"].value_counts().reindex(ROTULOS)

    fig, ax = plt.subplots()
    ax.bar(contagem.index, contagem.values)
    ax.set_title("RQ01 - Repositórios por faixa etária")
    ax.set_xlabel("faixa")
    ax.set_ylabel("repositórios")
    return salvar(fig, nome)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", default="lab01/data/sprint_s02/all_rqs.csv")
    args = parser.parse_args()

    setup_estilo()
    df = carregar_dados(args.entrada, ["repo", "age_years"])

    stats = resumo(df)
    print(
        f"RQ01 - {stats['repos']} repositórios | mediana {stats['mediana']} anos "
        f"(Q1 {stats['q1']}, Q3 {stats['q3']}, mín {stats['min']}, máx {stats['max']})"
    )

    caminho_hist = grafico_histograma(df, "rq01_histograma_idade")
    caminho_faixas = grafico_faixas(df, "rq01_faixas_idade")
    print(f"Gráficos salvos em {caminho_hist} e {caminho_faixas}")


if __name__ == "__main__":
    main()

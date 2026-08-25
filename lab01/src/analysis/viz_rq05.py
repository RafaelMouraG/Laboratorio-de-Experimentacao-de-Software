"""RQ05: sistemas populares são escritos nas linguagens mais populares? — primary_language.

Gráfico de barras horizontais das top 15 linguagens por número de repositórios, com destaque
visual de quais pertencem ao top 10 do TIOBE Index (constante TOP_LANGUAGES em analyze_rq07.py) —
é esse destaque que responde a pergunta, não a contagem sozinha. A categoria "sem linguagem
primária" (N/A) aparece como barra própria, nunca somada às demais.
"""

import argparse

import matplotlib.pyplot as plt
import pandas as pd

from analyze_rq07 import GRUPO_DEMAIS, GRUPO_NENHUMA, GRUPO_TOP, TOP_LANGUAGES
from viz_common import carregar_dados, salvar, setup_estilo

TOP_N = 15
COR_DESTAQUE = "#4C72B0"  
COR_SECUNDARIA = "#A8B2C4"    
SEM_LINGUAGEM = "N/A"


def classificar(linguagem: str) -> str:
    if linguagem == SEM_LINGUAGEM:
        return GRUPO_NENHUMA
    return GRUPO_TOP if linguagem in TOP_LANGUAGES else GRUPO_DEMAIS


def grafico_top_n(contagem: "pd.Series", nome: str) -> str:
    top = contagem.head(TOP_N).sort_values(ascending=True)
    grupos = [classificar(linguagem) for linguagem in top.index]
    cores = [
        COR_DESTAQUE if grupo == GRUPO_TOP else (COR_SECUNDARIA if grupo == GRUPO_DEMAIS else "grey")
        for grupo in grupos
    ]
    hatches = ["//" if grupo == GRUPO_NENHUMA else "" for grupo in grupos]

    fig, ax = plt.subplots()
    barras = ax.barh(top.index, top.values, color=cores, hatch=hatches)
    ax.bar_label(barras, label_type="edge", padding=3, fontsize=9)
    ax.set_title("RQ05 - Top 15 linguagens primárias nos 1.000 repositórios")
    ax.set_xlabel("repositórios")
    ax.set_xlim(0, top.max() * 1.18)
    ax.set_ylabel("")

    patches = [
        plt.Rectangle((0, 0), 1, 1, color=COR_DESTAQUE),
        plt.Rectangle((0, 0), 1, 1, color=COR_SECUNDARIA),
        plt.Rectangle((0, 0), 1, 1, color="grey", hatch="//"),
    ]
    ax.legend(patches, [GRUPO_TOP, GRUPO_DEMAIS, GRUPO_NENHUMA], loc="lower right")

    return salvar(fig, nome)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", default="lab01/data/sprint_s02/all_rqs.csv")
    args = parser.parse_args()

    setup_estilo()
    df = carregar_dados(args.entrada, ["repo", "primary_language"])
    total = len(df)
    contagem = df["primary_language"].value_counts()

    def reportar(grupo: str, condicao) -> None:
        n = int(condicao.sum())
        print(f"  {grupo}: {n} ({round(100 * n / total, 1)}%)")

    grupos = df["primary_language"].map(classificar)
    print(f"RQ05 - {total} repositórios | top 1 de linguagens mais populares: {', '.join(TOP_LANGUAGES)}")
    print(f"  linguagens distintas: {contagem.nunique()}")
    reportar(GRUPO_TOP, grupos == GRUPO_TOP)
    reportar(GRUPO_DEMAIS, grupos == GRUPO_DEMAIS)
    reportar(GRUPO_NENHUMA, grupos == GRUPO_NENHUMA)

    print(f"\nTop {TOP_N} linguagens por repositórios:")
    print(contagem.head(TOP_N).to_string())

    caminho = grafico_top_n(contagem, "rq05_top15_linguagens")
    print(f"Gráfico salvo em {caminho}")


if __name__ == "__main__":
    main()
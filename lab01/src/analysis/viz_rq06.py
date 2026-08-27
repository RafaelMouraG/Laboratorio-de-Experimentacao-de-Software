"""RQ06: sistemas populares possuem alto percentual de issues fechadas? — closed_issues_ratio.

Histograma com a mediana marcada e boxplot da razão fechadas/total, calculados apenas sobre os
repositórios com `total_issues > 0`. Os 43 com `total_issues == 0` ficam de fora do cálculo:
a coleta grava `closed_issues_ratio = 0.0` nesses casos (ver collect_all_rqs.py), o que cria
uma taxa falsamente baixa e derruba a mediana — mesmo recorte já declarado nas limitações da
metodologia (relatório, seção 2) e na validação de consistência da Lab01S02.
"""

import argparse

import matplotlib.pyplot as plt

from viz_common import carregar_dados, marcar_mediana, salvar, setup_estilo

FAIXAS = [("< 50%", 0.0, 0.5), ("50-75%", 0.5, 0.75), ("75-90%", 0.75, 0.9), ("> 90%", 0.9, 1.001)]


def resumo(serie) -> dict:
    return {
        "repos": len(serie),
        "mediana": round(serie.median() * 100, 2),
        "media": round(serie.mean() * 100, 2),
        "q1": round(serie.quantile(0.25) * 100, 2),
        "q3": round(serie.quantile(0.75) * 100, 2),
    }


def reportar_faixas(serie) -> None:
    for rotulo, lo, hi in FAIXAS:
        n = int(((serie >= lo) & (serie < hi)).sum())
        print(f"  {rotulo}: {n} ({round(100 * n / len(serie), 1)}%)")


def grafico_histograma(serie, nome: str) -> str:
    fig, ax = plt.subplots()
    ax.hist(serie, bins=25)
    ax.set_title(f"RQ06 - Razão de issues fechadas nos {len(serie)} repositórios com issues")
    ax.set_xlabel("razão fechadas/total")
    ax.set_ylabel("repositórios")
    mediana = round(serie.median() * 100, 1)
    marcar_mediana(ax, serie.median(), rotulo=f"mediana = {mediana}%")
    return salvar(fig, nome)


def grafico_boxplot(serie, nome: str) -> str:
    fig, ax = plt.subplots()
    ax.boxplot(serie, orientation="horizontal", tick_labels=["closed_issues_ratio"])
    ax.set_title(f"RQ06 - Boxplot da razão de issues fechadas ({len(serie)} repositórios)")
    ax.set_xlabel("razão fechadas/total")
    return salvar(fig, nome)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", default="lab01/data/sprint_s02/all_rqs.csv")
    args = parser.parse_args()

    setup_estilo()
    df = carregar_dados(args.entrada, ["repo", "total_issues", "closed_issues_ratio"])

    excluidos = int((df["total_issues"] == 0).sum())
    serie = df.loc[df["total_issues"] > 0, "closed_issues_ratio"]
    stats = resumo(serie)

    print(
        f"RQ06 - {stats['repos']} repositórios entram no cálculo "
        f"(de {len(df)}; {excluidos} excluídos por total_issues == 0)"
    )
    print(f"  mediana: {stats['mediana']}% (Q1 {stats['q1']}%, Q3 {stats['q3']}%)")
    print(f"  média: {stats['media']}%")
    print("  faixas:")
    reportar_faixas(serie)

    caminho_hist = grafico_histograma(serie, "rq06_histograma_ratio")
    caminho_box = grafico_boxplot(serie, "rq06_boxplot_ratio")
    print(f"Gráficos salvos em {caminho_hist} e {caminho_box}")


if __name__ == "__main__":
    main()
"""RQ02: sistemas populares recebem muita contribuição externa? — merged_pull_requests."""

import argparse

import matplotlib.pyplot as plt
import numpy as np

from viz_common import carregar_dados, marcar_mediana, salvar, setup_estilo


def resumo(serie) -> dict:
    return {
        "repos": len(serie),
        "zeros": int((serie == 0).sum()),
        "mediana": round(serie.median(), 2),
        "q1": round(serie.quantile(0.25), 2),
        "q3": round(serie.quantile(0.75), 2),
    }


def grafico_histograma(serie, nome: str) -> str:
    # Escala log no eixo X: repositório com 0 PRs não entra no histograma em log (log(0) é
    # indefinido) — por isso o recorte de zeros é reportado à parte, não no gráfico.
    positivos = serie[serie > 0]
    bins = np.logspace(np.log10(positivos.min()), np.log10(positivos.max()), 30)

    fig, ax = plt.subplots()
    ax.hist(positivos, bins=bins)
    ax.set_xscale("log")
    ax.set_title("RQ02 - Distribuição de pull requests aceitas (escala log)")
    ax.set_xlabel("pull requests aceitas (log)")
    ax.set_ylabel("repositórios")
    mediana = round(positivos.median(), 2)
    marcar_mediana(ax, mediana, rotulo=f"mediana (sem zeros) = {mediana}")
    return salvar(fig, nome)


def grafico_boxplot(serie, nome: str) -> str:
    # Escala log no eixo X pelo mesmo motivo do histograma: em escala linear a caixa fica
    # esmagada perto de zero e os outliers viram um amontoado ilegível de pontos.
    positivos = serie[serie > 0]

    fig, ax = plt.subplots()
    ax.boxplot(positivos, orientation="horizontal", tick_labels=["merged_pull_requests"])
    ax.set_xscale("log")
    ax.set_title("RQ02 - Boxplot de pull requests aceitas (escala log, sem zeros)")
    ax.set_xlabel("pull requests aceitas (log)")
    return salvar(fig, nome)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", default="lab01/data/sprint_s02/all_rqs.csv")
    args = parser.parse_args()

    setup_estilo()
    df = carregar_dados(args.entrada, ["repo", "merged_pull_requests"])
    serie = df["merged_pull_requests"]

    stats_todos = resumo(serie)
    stats_sem_zero = resumo(serie[serie > 0])
    print(
        f"RQ02 - {stats_todos['repos']} repositórios | {stats_todos['zeros']} com zero PRs "
        f"aceitas ({round(100 * stats_todos['zeros'] / stats_todos['repos'], 1)}%)"
    )
    print(
        f"  mediana (todos): {stats_todos['mediana']} (Q1 {stats_todos['q1']}, Q3 {stats_todos['q3']})"
    )
    print(
        f"  mediana (sem zeros): {stats_sem_zero['mediana']} "
        f"(Q1 {stats_sem_zero['q1']}, Q3 {stats_sem_zero['q3']})"
    )

    caminho_hist = grafico_histograma(serie, "rq02_histograma_prs_log")
    caminho_box = grafico_boxplot(serie, "rq02_boxplot_prs")
    print(f"Gráficos salvos em {caminho_hist} e {caminho_box}")


if __name__ == "__main__":
    main()

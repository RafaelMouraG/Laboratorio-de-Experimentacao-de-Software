"""Exemplo de uso do viz_common: histograma da idade dos repositórios (RQ01) com mediana marcada.

Serve de referência para os scripts de visualização das RQ01-RQ06 (issues #25-#30) e de prova de
que o pipeline `carregar_dados -> plotar -> salvar` funciona ponta a ponta.
"""

import argparse

import matplotlib.pyplot as plt

from viz_common import carregar_dados, marcar_mediana, salvar, setup_estilo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", default="lab01/data/sprint_s02/all_rqs.csv")
    parser.add_argument("--nome", default="exemplo_rq01_idade")
    args = parser.parse_args()

    setup_estilo()
    df = carregar_dados(args.entrada, ["age_years"])

    fig, ax = plt.subplots()
    ax.hist(df["age_years"], bins=30)
    ax.set_title("RQ01 - Distribuição da idade dos repositórios")
    ax.set_xlabel("idade (anos)")
    ax.set_ylabel("repositórios")
    marcar_mediana(ax, df["age_years"].median())

    caminho = salvar(fig, args.nome)
    print(f"Gráfico de exemplo salvo em {caminho}")


if __name__ == "__main__":
    main()

"""RQ03: sistemas populares lançam releases com frequência? — releases_por_ano e o recorte dos sem release.

A distribuição é bimodal: um grupo grande não usa *GitHub Releases* de jeito nenhum (275 dos
1.000, 27,5%) e outro publica com cadência alta. Por isso os gráficos separam os dois recortes em
vez de escondê-los num histograma único, e a resposta sai sempre com os dois números juntos:
6,78 releases/ano considerando todos e 14,94 entre os 725 que publicam. O total bruto de releases
fica como métrica secundária — favorece repositório antigo (ver README, análise da RQ03).
"""

import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analyze_rq03 import sem_release_por_linguagem
from viz_common import carregar_dados, marcar_mediana, salvar, setup_estilo

COLUNAS = ["repo", "primary_language", "releases", "age_years", "releases_por_ano", "sem_release"]

# Corte mínimo de repositórios para uma linguagem entrar no gráfico de percentual: sem ele, uma
# linguagem com um único repositório sem release vira barra de 100% e domina o eixo.
MIN_REPOS_LINGUAGEM = 10


def resumo(df: pd.DataFrame) -> dict:
    """Estatísticas dos dois recortes — sempre reportados juntos (critério de aceite da issue)."""
    com_release = df[~df["sem_release"]]
    return {
        "repos": len(df),
        "sem_release": int(df["sem_release"].sum()),
        "percentual_sem_release": round(100 * df["sem_release"].mean(), 1),
        "mediana_todos": round(df["releases_por_ano"].median(), 2),
        "mediana_com_release": round(com_release["releases_por_ano"].median(), 2),
        "mediana_releases_todos": round(df["releases"].median(), 2),
        "mediana_releases_com_release": round(com_release["releases"].median(), 2),
    }


def conferir_resumo(resumo_csv: pd.DataFrame, stats: dict) -> list[str]:
    """Compara as medianas recalculadas aqui com as do `rq03_resumo.csv` gerado pelo analyze_rq03.

    Os dois CSVs de entrada saem da mesma execução, mas nada impede que um seja regerado sem o
    outro. Como os números do relatório vêm daqui, vale a trava: devolve a lista de divergências
    (vazia quando bate), para o main avisar em vez de publicar gráfico e resumo discordando.
    """
    esperado = {
        ("releases_por_ano", "todos os repositórios"): stats["mediana_todos"],
        ("releases_por_ano", "apenas com release"): stats["mediana_com_release"],
        ("releases", "todos os repositórios"): stats["mediana_releases_todos"],
        ("releases", "apenas com release"): stats["mediana_releases_com_release"],
    }
    divergencias = []
    for (metrica, recorte), calculado in esperado.items():
        linha = resumo_csv[
            (resumo_csv["metrica"] == metrica) & (resumo_csv["recorte"] == recorte)
        ]
        if linha.empty:
            divergencias.append(f"{metrica} / {recorte}: ausente no resumo")
            continue
        do_csv = float(linha["mediana"].iloc[0])
        if abs(do_csv - calculado) > 0.01:
            divergencias.append(
                f"{metrica} / {recorte}: resumo {do_csv} != recalculado {calculado}"
            )
    return divergencias


def grafico_com_vs_sem(df: pd.DataFrame, nome: str) -> str:
    contagem = df["sem_release"].value_counts()
    rotulos = ["com release", "sem release"]
    valores = [int(contagem.get(False, 0)), int(contagem.get(True, 0))]
    percentuais = [100 * valor / len(df) for valor in valores]

    fig, ax = plt.subplots()
    barras = ax.bar(rotulos, valores)
    for barra, valor, percentual in zip(barras, valores, percentuais):
        ax.text(
            barra.get_x() + barra.get_width() / 2,
            valor,
            f"{valor} ({percentual:.1f}%)".replace(".", ","),
            ha="center",
            va="bottom",
        )
    ax.set_title("RQ03 - Repositórios que publicam vs. não publicam release")
    ax.set_ylabel("repositórios")
    ax.set_ylim(0, max(valores) * 1.15)
    return salvar(fig, nome)


def grafico_histograma(df: pd.DataFrame, nome: str) -> str:
    # Escala log no eixo X pelo mesmo motivo do viz_rq02: entre os 725 que publicam a cadência vai
    # de menos de 1 a milhares de releases por ano, e em escala linear a cauda esmaga todos os bins.
    com_release = df.loc[~df["sem_release"], "releases_por_ano"]
    positivos = com_release[com_release > 0]
    bins = np.logspace(np.log10(positivos.min()), np.log10(positivos.max()), 30)

    fig, ax = plt.subplots()
    ax.hist(positivos, bins=bins)
    ax.set_xscale("log")
    ax.set_title("RQ03 - Releases por ano (apenas os que publicam release)")
    ax.set_xlabel("releases por ano (log)")
    ax.set_ylabel("repositórios")
    mediana = round(positivos.median(), 2)
    marcar_mediana(ax, mediana, rotulo=f"mediana = {mediana}")
    return salvar(fig, nome)


def grafico_sem_release_por_linguagem(df: pd.DataFrame, nome: str) -> str:
    tabela = sem_release_por_linguagem(df, min_repos=MIN_REPOS_LINGUAGEM)

    fig, ax = plt.subplots(figsize=(8, max(4, 0.35 * len(tabela))))
    ax.barh(tabela.index[::-1], tabela["percentual_sem_release"][::-1])
    invertida = tabela[::-1]
    for i, percentual, sem_release, repos in zip(
        range(len(invertida)),
        invertida["percentual_sem_release"],
        invertida["sem_release"],
        invertida["repos"],
    ):
        # A fração absoluta ao lado do percentual evita a leitura de que 90,9% em HTML valem para a
        # linguagem inteira: são 10 de 11 repositórios da amostra.
        ax.text(
            percentual + 1.5,
            i,
            f"{percentual:.1f}%".replace(".", ",") + f" ({int(sem_release)}/{int(repos)})",
            va="center",
        )
    ax.set_title("RQ03 - Repositórios sem release por linguagem primária")
    ax.set_xlabel(f"% sem release (linguagens com ao menos {MIN_REPOS_LINGUAGEM} repositórios)")
    # Folga além de 100% para o rótulo das barras mais longas não sair cortado na borda.
    ax.set_xlim(0, 122)
    ax.set_xticks(range(0, 101, 20))
    return salvar(fig, nome)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", default="lab01/data/sprint_s02/rq03_releases_por_ano.csv")
    parser.add_argument("--resumo", default="lab01/data/sprint_s02/rq03_resumo.csv")
    args = parser.parse_args()

    setup_estilo()
    # `assign` em vez de atribuir na coluna: `carregar_dados` devolve um recorte (`df[colunas]`) e
    # escrever nele direto é atribuição encadeada, que deixa de funcionar no pandas 3.
    df = carregar_dados(args.entrada, COLUNAS)
    df = df.assign(sem_release=df["sem_release"].astype(bool))

    stats = resumo(df)
    print(
        f"RQ03 - {stats['repos']} repositórios | {stats['sem_release']} sem nenhuma release "
        f"({stats['percentual_sem_release']}% da amostra)"
    )
    print(
        f"  releases_por_ano - mediana (todos): {stats['mediana_todos']} | "
        f"mediana (apenas com release): {stats['mediana_com_release']}"
    )
    print(
        f"  total bruto (métrica secundária, favorece repositório antigo) - "
        f"mediana (todos): {stats['mediana_releases_todos']} | "
        f"mediana (apenas com release): {stats['mediana_releases_com_release']}"
    )

    divergencias = conferir_resumo(carregar_dados(args.resumo), stats)
    if divergencias:
        print(f"  AVISO - {args.resumo} discorda dos dados por repositório:")
        for divergencia in divergencias:
            print(f"    {divergencia}")

    caminho_barras = grafico_com_vs_sem(df, "rq03_com_vs_sem_release")
    caminho_hist = grafico_histograma(df, "rq03_histograma_releases_por_ano")
    caminho_linguagens = grafico_sem_release_por_linguagem(df, "rq03_sem_release_por_linguagem")
    print(f"Gráficos salvos em {caminho_barras}, {caminho_hist} e {caminho_linguagens}")


if __name__ == "__main__":
    main()

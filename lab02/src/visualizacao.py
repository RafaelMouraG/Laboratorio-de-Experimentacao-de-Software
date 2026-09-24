#!/usr/bin/env python3
"""Gráficos comparando com_ia x sem_ia: RQ1, RQ2 e RQ3 (Issue #64)."""

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

RAIZ = Path(__file__).resolve().parents[1]
CSV = RAIZ / "data" / "trials.csv"
SAIDA = RAIZ / "figuras"
WILCOXON_RQ1 = RAIZ / "resultados" / "rq1_wilcoxon.csv"  # gerado por analise_descritiva.py (#61)

TRATAMENTOS = ["com_ia", "sem_ia"]
ROTULOS = {"com_ia": "Com IA", "sem_ia": "Sem IA"}
CORES = {"com_ia": "#2a78d6", "sem_ia": "#eb6834"}
TIME_BOX = 2100

TEXTO = "#0b0b0b"
TEXTO_2 = "#52514e"
GRADE = "#e4e3df"
FUNDO = "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": FUNDO,
    "axes.facecolor": FUNDO,
    "savefig.facecolor": FUNDO,
    "axes.edgecolor": GRADE,
    "axes.labelcolor": TEXTO_2,
    "axes.titlecolor": TEXTO,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.grid.axis": "y",
    "axes.axisbelow": True,
    "grid.color": GRADE,
    "grid.linewidth": 0.8,
    "xtick.color": TEXTO_2,
    "ytick.color": TEXTO_2,
    "font.size": 10,
    "legend.frameon": False,
})


def censurados(df):
    return df["censurado_35min"].astype(str).str.lower() == "true"


def eixo_tratamento(ax):
    ax.set_xticks(range(len(TRATAMENTOS)), [ROTULOS[t] for t in TRATAMENTOS])
    ax.set_xlim(-0.6, len(TRATAMENTOS) - 0.4)
    ax.tick_params(axis="x", length=0)


def box_com_pontos(ax, df, col, marcar_censurados=False, fmt="{:.4g}"):
    """Boxplot por tratamento com os trials sobrepostos (N pequeno: mostrar todos)."""
    rng = np.random.default_rng(0)
    for i, t in enumerate(TRATAMENTOS):
        sub = df[df["tratamento"] == t]
        ax.boxplot(
            sub[col], positions=[i], widths=0.45, patch_artist=True, showfliers=False,
            boxprops={"facecolor": CORES[t] + "33", "edgecolor": CORES[t], "linewidth": 1.5},
            medianprops={"color": CORES[t], "linewidth": 2.5},
            whiskerprops={"color": CORES[t], "linewidth": 1.5},
            capprops={"color": CORES[t], "linewidth": 1.5},
        )
        x = i + rng.uniform(-0.12, 0.12, len(sub))
        cens = censurados(sub).to_numpy() if marcar_censurados else np.zeros(len(sub), bool)
        ax.scatter(x[~cens], sub[col][~cens], s=40, color=CORES[t], edgecolor=FUNDO, linewidth=1.5, zorder=3)
        ax.scatter(x[cens], sub[col][cens], s=70, marker="X", color=CORES[t], edgecolor=TEXTO, linewidth=0.8, zorder=3)
        med = sub[col].median()
        ax.annotate(fmt.format(med), (i + 0.25, med), xytext=(4, 0), textcoords="offset points",
                    va="center", fontsize=9, color=TEXTO)
    eixo_tratamento(ax)


def espalhar(ys, folga=0.09):
    """Posições (log) para os rótulos da direita não se sobreporem."""
    ordem = np.argsort(ys)
    log = np.log10(np.asarray(ys, float))[ordem]
    for i in range(1, len(log)):
        log[i] = max(log[i], log[i - 1] + folga)
    saida = np.empty_like(log)
    saida[ordem] = 10 ** log
    return saida


def rodape(fig, df, extra=""):
    n = df["tratamento"].value_counts()
    texto = f"Fonte: lab02/data/trials.csv · {len(df)} trials ({n.get('com_ia', 0)} com IA, {n.get('sem_ia', 0)} sem IA)"
    fig.text(0.01, 0.01, texto + (f"\n{extra}" if extra else ""), fontsize=8, color=TEXTO_2, va="bottom")


def eixo_tempo(ax):
    """Escala log: com_ia e sem_ia diferem em mais de uma ordem de grandeza."""
    ax.set_yscale("log")
    ax.set_ylim(20, TIME_BOX * 1.5)
    ax.set_yticks([20, 50, 100, 200, 500, 1000])
    ax.yaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_ylabel("tempo até verde (s, escala log)")
    ax.axhline(TIME_BOX, color=TEXTO_2, linestyle="--", linewidth=1)
    ax.text(-0.55, TIME_BOX, "time-box 35 min (2100 s)", va="bottom", fontsize=8.5, color=TEXTO_2)


def legenda_censurados(ax, df):
    n = int(censurados(df).sum())
    rotulo = f"censurado no time-box ({n})"
    ax.legend(handles=[Line2D([], [], marker="X", linestyle="", color=TEXTO_2, markersize=8, label=rotulo)],
              loc="lower right", fontsize=8.5)


def fig_rq1_tempo(df):
    fig, ax = plt.subplots(figsize=(6, 5))
    box_com_pontos(ax, df, "tempo_s", marcar_censurados=True)
    eixo_tempo(ax)
    legenda_censurados(ax, df)
    ax.set_title("RQ1: tempo por tratamento", loc="left")
    rodape(fig, df)
    return fig


def fig_rq1_pareado(df):
    """Uma linha por par (integrante, bloco de ordem 1-2 / 3-4), o mesmo pareamento do Wilcoxon."""
    df = df.assign(bloco=(df["ordem"] + 1) // 2)
    fig, ax = plt.subplots(figsize=(7, 5))
    rotulos = []
    for (integrante, _), par in df.groupby(["integrante", "bloco"]):
        par = par.set_index("tratamento").reindex(TRATAMENTOS)
        if par["tempo_s"].isna().any():
            continue
        ax.plot(range(len(TRATAMENTOS)), par["tempo_s"], color=TEXTO_2, linewidth=1.5, alpha=0.6, zorder=1)
        for i, t in enumerate(TRATAMENTOS):
            cens = censurados(par.loc[[t]]).iloc[0]
            ax.scatter(i, par.loc[t, "tempo_s"], s=70 if cens else 45, marker="X" if cens else "o",
                       color=CORES[t], edgecolor=TEXTO if cens else FUNDO, linewidth=1.5, zorder=3)
        rotulos.append((par.loc["sem_ia", "tempo_s"],
                        f"{integrante} ({par.loc['com_ia', 'kata']} com / {par.loc['sem_ia', 'kata']} sem)"))
    for y, (y_ponto, texto) in zip(espalhar([r[0] for r in rotulos]), rotulos):
        ax.annotate(texto, (1, y_ponto), xytext=(1.08, y), textcoords="data", va="center",
                    fontsize=8.5, color=TEXTO, arrowprops={"arrowstyle": "-", "color": TEXTO_2, "linewidth": 0.6, "relpos": (0, 0.5)})
    eixo_tratamento(ax)
    ax.set_xlim(-0.3, 2.1)
    eixo_tempo(ax)
    legenda_censurados(ax, df)
    ax.set_title("RQ1: tempo pareado por integrante", loc="left")
    teste = ""
    if WILCOXON_RQ1.exists():
        w = pd.read_csv(WILCOXON_RQ1).iloc[0]
        teste = (f"Wilcoxon pareado exato, unilateral (com IA < sem IA): p = {w.p_valor:.4f} · "
                 f"rank-biserial = {w.rank_biserial:.2f} · {int(w.n_pares)} pares")
    rodape(fig, df, teste)
    return fig


def fig_rq2(df):
    """Distribuição por trial, não barra de mediana: a barra esconderia um trial com falha."""
    fig, ax = plt.subplots(figsize=(6, 5))
    box_com_pontos(ax, df, "taxa_sucesso", fmt="{:.0%}")
    for i, t in enumerate(TRATAMENTOS):
        sub = df[df["tratamento"] == t]
        todos = int((sub["taxa_sucesso"] == 1).sum())
        falhando = int((sub["testes_total"] - sub["testes_passando"]).sum())
        ax.annotate(f"{todos}/{len(sub)} trials com 100%\n{falhando} testes falhando", (i, 1),
                    xytext=(0, -28), textcoords="offset points", ha="center", va="top",
                    fontsize=9, color=TEXTO)
    ax.set_ylim(0, 1.05)
    ax.set_yticks(np.linspace(0, 1, 5))
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
    ax.set_ylabel("taxa de sucesso (testes passando)")
    ax.set_title("RQ2: taxa de sucesso por tratamento", loc="left")
    rodape(fig, df)
    return fig


def fig_rq3(df):
    metricas = [
        ("loc", "LOC (controle de tamanho)"),
        ("cc_media", "complexidade ciclomática média"),
        ("duplicacao_pct", "duplicação (%)"),
        ("mi", "índice de manutenibilidade"),
    ]
    fig, axs = plt.subplots(1, len(metricas), figsize=(14, 4.8))
    for ax, (col, rotulo) in zip(axs, metricas):
        sub = df.dropna(subset=[col])
        box_com_pontos(ax, sub, col)
        ax.set_title(rotulo, loc="left", fontsize=10.5)
        if sub[col].nunique() == 1:
            ax.set_ylim(0, max(1, 2 * sub[col].iloc[0]))
            ax.text(0.5, 0.75, f"sem variação: {sub[col].iloc[0]:g} em todos os {len(sub)} trials",
                    transform=ax.transAxes, ha="center", fontsize=9, color=TEXTO_2)
        else:
            ax.set_ylim(bottom=0)
    axs[3].set_ylim(0, 100)
    fig.suptitle("RQ3: métricas estáticas por tratamento", x=0.01, ha="left", fontweight="bold", color=TEXTO)
    fig.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=CORES[t]) for t in TRATAMENTOS],
               labels=[ROTULOS[t] for t in TRATAMENTOS], loc="upper right", ncol=2)
    rodape(fig, df)
    return fig


def fig_rq3_cc_loc(df):
    """cc_media contra loc: mostra se a diferença de complexidade vem só do tamanho."""
    fig, ax = plt.subplots(figsize=(6, 5))
    for t in TRATAMENTOS:
        sub = df[df["tratamento"] == t].dropna(subset=["loc", "cc_media"])
        ax.scatter(sub["loc"], sub["cc_media"], s=55, color=CORES[t], alpha=0.85,
                   edgecolor=FUNDO, linewidth=2, label=ROTULOS[t], zorder=3)
    ax.grid(axis="x")
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("LOC (sloc)")
    ax.set_ylabel("complexidade ciclomática média")
    ax.legend(loc="upper left")
    ax.set_title("RQ3: complexidade × tamanho", loc="left")
    rodape(fig, df)
    return fig


def main():
    df = pd.read_csv(CSV)
    SAIDA.mkdir(exist_ok=True)
    figuras = {
        "rq1_tempo_boxplot.png": fig_rq1_tempo(df),
        "rq1_tempo_pareado.png": fig_rq1_pareado(df),
        "rq2_taxa_sucesso.png": fig_rq2(df),
        "rq3_metricas_estaticas.png": fig_rq3(df),
        "rq3_cc_vs_loc.png": fig_rq3_cc_loc(df),
    }
    for nome, fig in figuras.items():
        fig.tight_layout(rect=(0, 0.07 if nome == "rq1_tempo_pareado.png" else 0.04, 1, 1))
        fig.savefig(SAIDA / nome, dpi=150)
        plt.close(fig)
        print(os.path.relpath(SAIDA / nome))


if __name__ == "__main__":
    main()

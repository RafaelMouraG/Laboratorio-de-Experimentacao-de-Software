"""Infraestrutura comum de gráficos para as RQs — leitura de dados, estilo e salvamento.

Centraliza o que antes estava duplicado em cada script de análise (`carregar` reaparecia quase
idêntico em analyze_rq03.py, analyze_rq05_rq06.py, analyze_rq07.py e
extra_idade_vs_popularidade.py) e adiciona o que falta para gerar os gráficos da Lab01S03:
estilo visual único e salvamento padronizado em `lab01/relatorio/figuras/`.
"""

from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt
import pandas as pd

FIGURAS_DIR = "lab01/relatorio/figuras"

# Paleta e estilo únicos para manter os gráficos visualmente consistentes no relatório final.
PALETA = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B2", "#937860"]
COR_MEDIANA = "#C44E52"

_ESTILO_APLICADO = False


def carregar_dados(caminho: str, colunas: list[str] | None = None) -> pd.DataFrame:
    """Lê um CSV de coleta com a convenção usada em todas as RQs.

    `keep_default_na=False` evita que o pandas trate a string "N/A" de `primary_language` como
    valor ausente (ver limitação 2 do README) e descarte essas linhas em silêncio no groupby.
    Quando `colunas` é informado, valida que todas existem antes de recortar o DataFrame — mesmo
    comportamento que os scripts de análise já tinham individualmente.
    """
    if not os.path.exists(caminho):
        sys.exit(f"{caminho} não encontrado. Rode antes os scripts de coleta das RQ01-RQ06.")

    df = pd.read_csv(caminho, keep_default_na=False)
    if colunas is not None:
        faltando = [coluna for coluna in colunas if coluna not in df.columns]
        if faltando:
            sys.exit(f"{caminho}: colunas ausentes {faltando}")
        return df[colunas]
    return df


def setup_estilo() -> None:
    """Aplica o estilo visual único (fonte, grid, paleta) a todos os gráficos do relatório.

    Idempotente: chamar mais de uma vez não acumula configuração. Cada script de RQ deve chamar
    isso antes de criar as figuras, para não depender da ordem de importação entre módulos.
    """
    global _ESTILO_APLICADO
    if _ESTILO_APLICADO:
        return

    plt.rcParams.update(
        {
            "figure.figsize": (8, 5),
            "figure.dpi": 100,
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.labelsize": 11,
            "axes.grid": True,
            "grid.alpha": 0.3,
            "grid.linestyle": "--",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.prop_cycle": plt.cycler(color=PALETA),
            "legend.frameon": False,
        }
    )
    _ESTILO_APLICADO = True


def marcar_mediana(ax: plt.Axes, valor: float, rotulo: str | None = None, eixo: str = "x") -> None:
    """Desenha uma linha na mediana (vertical por padrão) com um rótulo de texto ao lado.

    `eixo="x"` marca uma mediana calculada sobre os valores do eixo x (ex.: histograma); use
    `eixo="y"` para marcar uma mediana no eixo y (ex.: barras horizontais).
    """
    texto = rotulo if rotulo is not None else f"mediana = {valor:g}"
    if eixo == "x":
        ax.axvline(valor, color=COR_MEDIANA, linestyle="--", linewidth=1.5)
        ax.text(
            valor,
            ax.get_ylim()[1] * 0.97,
            f" {texto}",
            color=COR_MEDIANA,
            va="top",
            ha="left",
        )
    elif eixo == "y":
        ax.axhline(valor, color=COR_MEDIANA, linestyle="--", linewidth=1.5)
        ax.text(
            ax.get_xlim()[1] * 0.97,
            valor,
            f" {texto}",
            color=COR_MEDIANA,
            va="bottom",
            ha="right",
        )
    else:
        raise ValueError(f"eixo inválido: {eixo!r} (use 'x' ou 'y')")


def salvar(fig: plt.Figure, nome: str, pasta: str = FIGURAS_DIR) -> str:
    """Salva a figura em PNG a 150 dpi em `lab01/relatorio/figuras/<nome>.png`.

    Retorna o caminho salvo, para o script de análise poder confirmar no log.
    """
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f"{nome}.png")
    fig.savefig(caminho, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return caminho

"""Testes não paramétricos e tamanhos de efeito usados nas comparações entre grupos."""

from __future__ import annotations

from typing import Sequence

import pandas as pd
from scipy.stats import kruskal, mannwhitneyu

# Cortes de Romano et al. (2006) para |delta| de Cliff.
CORTES_MAGNITUDE = ((0.147, "negligenciavel"), (0.33, "pequeno"), (0.474, "medio"))


def epsilon_quadrado(h: float, n: int) -> float:
    """Tamanho de efeito do Kruskal-Wallis: ``H / (n - 1)``."""
    if n < 2:
        raise ValueError("epsilon² precisa de pelo menos duas observações")
    return h / (n - 1)


def cliffs_delta(x: Sequence[float], y: Sequence[float]) -> float:
    """Delta de Cliff ``2·U₁ / (n₁·n₂) - 1``; positivo quando ``x`` tende a ser maior."""
    if len(x) == 0 or len(y) == 0:
        raise ValueError("delta de Cliff precisa de dois grupos não vazios")
    u1 = mannwhitneyu(x, y).statistic
    return float(2 * u1 / (len(x) * len(y)) - 1)


def magnitude(delta: float) -> str:
    """Interpretação de |delta| pelos cortes de Romano et al."""
    absoluto = abs(delta)
    for corte, nome in CORTES_MAGNITUDE:
        if absoluto < corte:
            return nome
    return "grande"


def comparar_grupos(df: pd.DataFrame, fator: str, metrica: str) -> dict:
    """Compara ``metrica`` entre os grupos de ``fator``.

    Usa Kruskal-Wallis (efeito: epsilon²) com três grupos ou mais e Mann-Whitney
    bilateral (efeito: delta de Cliff) com dois. Linhas sem fator ou sem métrica
    ficam de fora e são contadas em ``ausentes``.
    """
    validos = df[[fator, metrica]].dropna()
    grupos = {
        nome: grupo[metrica].to_numpy()
        for nome, grupo in validos.groupby(fator, observed=True)
    }
    if len(grupos) < 2:
        raise ValueError(f"{fator} tem menos de dois grupos com {metrica}")
    n = len(validos)
    if len(grupos) == 2:
        x, y = grupos.values()
        estatistica, p_valor = mannwhitneyu(x, y, alternative="two-sided")
        teste, efeito, nome_efeito = "mann-whitney", cliffs_delta(x, y), "delta_cliff"
    else:
        estatistica, p_valor = kruskal(*grupos.values())
        teste, efeito, nome_efeito = "kruskal-wallis", epsilon_quadrado(estatistica, n), "epsilon2"
    return {
        "fator": fator,
        "metrica": metrica,
        "teste": teste,
        "grupos": len(grupos),
        "n": n,
        "ausentes": len(df) - n,
        "estatistica": float(estatistica),
        "p_valor": float(p_valor),
        "efeito": float(efeito),
        "nome_efeito": nome_efeito,
    }

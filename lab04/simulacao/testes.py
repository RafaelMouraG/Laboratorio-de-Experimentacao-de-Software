"""Os dois testes e o tamanho de efeito de cada um, vetorizados ao longo de `axis`.

Com as matrizes do gerador (uma linha por conjunto), `axis=-1` roda as 10.000 repetições de uma vez.

Escolhas do Mann-Whitney:

- `alternative="two-sided"`, porque as hipóteses do `cenario.md` são bicaudais.
- `method="asymptotic"`, com correção de continuidade. O `"auto"` troca de método conforme o n e os
  empates, e a regra mudou entre versões do scipy (a CI usa a 1.13), então a taxa de erro poderia
  mudar de uma situação da Q3 para outra só pelo método. Fixando a aproximação normal de U, todas
  as situações usam o mesmo teste e as repetições continuam rápidas. O custo é que com n = 10 o
  p-valor é aproximado, o que entra na leitura da Q3.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

ALTERNATIVA = "two-sided"
METODO_MW = "asymptotic"


@dataclass(frozen=True)
class Resultado:
    estatistica: np.ndarray
    p: np.ndarray


def welch(x, y, axis: int = -1) -> Resultado:
    """t de Welch: compara as médias sem supor variâncias iguais."""
    r = stats.ttest_ind(x, y, equal_var=False, axis=axis, alternative=ALTERNATIVA)
    return Resultado(np.asarray(r.statistic), np.asarray(r.pvalue))


def mann_whitney(x, y, axis: int = -1) -> Resultado:
    """Mann-Whitney: a estatística é o U do primeiro grupo."""
    r = stats.mannwhitneyu(
        x, y, use_continuity=True, alternative=ALTERNATIVA, method=METODO_MW, axis=axis
    )
    return Resultado(np.asarray(r.statistic), np.asarray(r.pvalue))


def g_hedges(x, y, axis: int = -1) -> np.ndarray:
    """g de Hedges: diferença das médias sobre o desvio combinado, com a correção de viés J."""
    x, y = np.moveaxis(np.asarray(x, float), axis, -1), np.moveaxis(np.asarray(y, float), axis, -1)
    n1, n2 = x.shape[-1], y.shape[-1]
    var = ((n1 - 1) * x.var(axis=-1, ddof=1) + (n2 - 1) * y.var(axis=-1, ddof=1)) / (n1 + n2 - 2)
    d = (x.mean(axis=-1) - y.mean(axis=-1)) / np.sqrt(var)
    return d * (1 - 3 / (4 * (n1 + n2) - 9))


def delta_cliff(x, y, axis: int = -1) -> np.ndarray:
    """δ de Cliff: P(X > Y) − P(X < Y), de −1 a 1. Empates contam meio para cada lado.

    Sai do U pelos postos (δ = 2U / n1n2 − 1), sem montar a matriz de todos os pares.
    """
    x, y = np.moveaxis(np.asarray(x, float), axis, -1), np.moveaxis(np.asarray(y, float), axis, -1)
    n1, n2 = x.shape[-1], y.shape[-1]
    postos = stats.rankdata(np.concatenate([x, y], axis=-1), axis=-1)
    u = postos[..., :n1].sum(axis=-1) - n1 * (n1 + 1) / 2
    return 2 * u / (n1 * n2) - 1

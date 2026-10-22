import math

import pandas as pd

from lab03.analise.comum import resumo


def test_resumo_com_serie_completa():
    resultado = resumo(pd.Series([1, 2, 3, 4]))
    assert resultado == {
        "n": 4,
        "ausentes": 0,
        "mediana": 2.5,
        "q1": 1.75,
        "q3": 3.25,
        "iqr": 1.5,
    }


def test_resumo_ignora_e_conta_nan():
    resultado = resumo(pd.Series([1, float("nan"), 3, None]))
    assert resultado == {
        "n": 2,
        "ausentes": 2,
        "mediana": 2.0,
        "q1": 1.5,
        "q3": 2.5,
        "iqr": 1.0,
    }


def test_resumo_serie_vazia():
    resultado = resumo(pd.Series([], dtype="float64"))
    assert resultado["n"] == 0
    assert resultado["ausentes"] == 0
    assert all(math.isnan(resultado[chave]) for chave in ("mediana", "q1", "q3", "iqr"))


def test_resumo_serie_somente_com_nan():
    resultado = resumo(pd.Series([float("nan"), float("nan")]))
    assert resultado["n"] == 0
    assert resultado["ausentes"] == 2
    assert all(math.isnan(resultado[chave]) for chave in ("mediana", "q1", "q3", "iqr"))

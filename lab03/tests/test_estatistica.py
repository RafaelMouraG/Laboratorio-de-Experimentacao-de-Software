import math

import pandas as pd
import pytest

from lab03.analise.estatistica import cliffs_delta, comparar_grupos, epsilon_quadrado, magnitude


def test_cliffs_delta_grupos_totalmente_separados():
    assert cliffs_delta([4, 5, 6], [1, 2, 3]) == 1.0
    assert cliffs_delta([1, 2, 3], [4, 5, 6]) == -1.0


def test_cliffs_delta_grupos_iguais():
    assert cliffs_delta([1, 2, 3], [1, 2, 3]) == 0.0


def test_cliffs_delta_contagem_a_mao():
    # Pares (x, y): 3>1, 3>2, 1=1, 1<2 -> (2 - 1) / 4 = 0,25.
    assert cliffs_delta([3, 1], [1, 2]) == pytest.approx(0.25)


def test_cliffs_delta_grupo_vazio():
    with pytest.raises(ValueError):
        cliffs_delta([], [1, 2])


@pytest.mark.parametrize(
    ("delta", "esperado"),
    [
        (0, "negligenciavel"),
        (0.146, "negligenciavel"),
        (0.147, "pequeno"),
        (0.329, "pequeno"),
        (0.33, "medio"),
        (0.473, "medio"),
        (0.474, "grande"),
        (1, "grande"),
        (-0.5, "grande"),
        (-0.2, "pequeno"),
    ],
)
def test_magnitude_cortes_de_romano(delta, esperado):
    assert magnitude(delta) == esperado


def test_epsilon_quadrado_com_h_e_n_conhecidos():
    assert epsilon_quadrado(9.0, 10) == 1.0
    assert epsilon_quadrado(2.5, 11) == 0.25


def test_epsilon_quadrado_n_pequeno():
    with pytest.raises(ValueError):
        epsilon_quadrado(1.0, 1)


def test_comparar_grupos_dois_grupos_usa_mann_whitney():
    df = pd.DataFrame({"fator": ["a"] * 3 + ["b"] * 3, "metrica": [4, 5, 6, 1, 2, 3]})
    resultado = comparar_grupos(df, "fator", "metrica")
    assert resultado["teste"] == "mann-whitney"
    assert resultado["nome_efeito"] == "delta_cliff"
    assert resultado["efeito"] == 1.0
    assert resultado["estatistica"] == 9.0
    assert resultado["p_valor"] == pytest.approx(0.1)
    assert (resultado["n"], resultado["grupos"], resultado["ausentes"]) == (6, 2, 0)


def test_comparar_grupos_tres_grupos_usa_kruskal_wallis():
    # Postos 1-2-3, 4-5-6, 7-8-9: H = 12 / (9·10) · 3 · (2² + 5² + 8²) - 3·10 = 7,2.
    df = pd.DataFrame({"fator": list("aaabbbccc"), "metrica": range(1, 10)})
    resultado = comparar_grupos(df, "fator", "metrica")
    assert resultado["teste"] == "kruskal-wallis"
    assert resultado["estatistica"] == pytest.approx(7.2)
    assert resultado["efeito"] == pytest.approx(7.2 / 8)
    assert resultado["p_valor"] == pytest.approx(math.exp(-3.6))


def test_comparar_grupos_tira_e_conta_ausentes():
    df = pd.DataFrame({
        "fator": ["a", "a", "a", "b", "b", "b", None],
        "metrica": [4, 5, None, 1, 2, 3, 10],
    })
    resultado = comparar_grupos(df, "fator", "metrica")
    assert (resultado["n"], resultado["ausentes"]) == (5, 2)
    assert resultado["efeito"] == 1.0


def test_comparar_grupos_exige_dois_grupos():
    df = pd.DataFrame({"fator": ["a", "a"], "metrica": [1, 2]})
    with pytest.raises(ValueError):
        comparar_grupos(df, "fator", "metrica")

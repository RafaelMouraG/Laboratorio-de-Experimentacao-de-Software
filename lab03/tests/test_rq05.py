import math

import pandas as pd
import pytest

from lab03.analise.rq05 import correlacao, correlacoes, zeros


def test_correlacao_monotonica_perfeita():
    # Relação não linear, mas monotônica: os postos coincidem.
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [1, 4, 9, 16, 100]})
    resultado = correlacao(df, "x", "y")
    assert resultado["rho"] == pytest.approx(1.0)
    assert resultado["p_valor"] < 0.05
    assert (resultado["n"], resultado["ausentes"]) == (5, 0)


def test_correlacao_inversa_perfeita():
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [0.9, 0.5, 0.3, 0.2, 0.0]})
    assert correlacao(df, "x", "y")["rho"] == pytest.approx(-1.0)


def test_correlacao_tira_e_conta_linhas_com_nan():
    # Sem as linhas 2 e 4 sobram x = 1, 3, 5, 6 e y = 4, 3, 2, 1: inversa perfeita.
    df = pd.DataFrame({
        "x": [1, None, 3, 4, 5, 6],
        "y": [4, 10, 3, None, 2, 1],
    })
    resultado = correlacao(df, "x", "y")
    assert (resultado["n"], resultado["ausentes"]) == (4, 2)
    assert resultado["rho"] == pytest.approx(-1.0)


def test_correlacao_com_empates_contagem_a_mao():
    # Postos de y com empate: 1,5 1,5 3 4. d² = 0,25 + 0,25 + 0 + 0 = 0,5.
    # Com empates o Spearman é o Pearson dos postos: cov / (dp_x · dp_y).
    df = pd.DataFrame({"x": [1, 2, 3, 4], "y": [0, 0, 1, 2]})
    postos_x = [1, 2, 3, 4]
    postos_y = [1.5, 1.5, 3, 4]
    media = 2.5
    cov = sum((a - media) * (b - media) for a, b in zip(postos_x, postos_y))
    dp_x = math.sqrt(sum((a - media) ** 2 for a in postos_x))
    dp_y = math.sqrt(sum((b - media) ** 2 for b in postos_y))
    assert correlacao(df, "x", "y")["rho"] == pytest.approx(cov / (dp_x * dp_y))


def test_correlacao_exige_tres_repositorios():
    df = pd.DataFrame({"x": [1, 2, None], "y": [1, 2, 3]})
    with pytest.raises(ValueError):
        correlacao(df, "x", "y")


def test_correlacoes_checagem_sem_cfr_zero():
    df = pd.DataFrame({
        "releases_por_semana": [0.1, 0.2, 0.5, 1.0, 2.0, 4.0],
        "cfr_ci": [0.3, 0.2, 0.2, 0.1, 0.05, 0.0],
        "cfr_entrega": [0.0, 0.0, 0.1, 0.2, 0.4, None],
    })
    tabela = correlacoes(df).set_index(["recorte", "y"])
    assert tabela.loc[("todos", "cfr_ci"), "n"] == 6
    assert tabela.loc[("todos", "cfr_entrega"), ["n", "ausentes"]].tolist() == [5, 1]
    sem_zeros = tabela.loc[("sem_cfr_zero", "cfr_entrega")]
    assert (sem_zeros["n"], sem_zeros["ausentes"]) == (3, 1)
    assert sem_zeros["rho"] == pytest.approx(1.0)


def test_zeros_conta_cfr_igual_a_zero():
    df = pd.DataFrame({"cfr_ci": [0.0, 0.1, 0.0], "cfr_entrega": [0.0, None, 0.2]})
    contagem = zeros(df).set_index("metrica")
    assert contagem.loc["cfr_ci", ["zeros", "n"]].tolist() == [2, 3]
    assert contagem.loc["cfr_entrega", ["zeros", "n"]].tolist() == [1, 2]

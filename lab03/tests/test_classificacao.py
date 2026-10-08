import pytest

from lab03.metricas.classificacao import (
    RELEASES_POR_SEMANA_MEDIUM,
    classificacao_geral,
    faixa_cfr,
    faixa_frequencia,
    faixa_lead_time,
    faixa_recuperacao,
)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [(7, 4), (1, 3), (RELEASES_POR_SEMANA_MEDIUM, 2), (0, 1), (None, None)],
)
def test_faixa_frequencia_limites(valor, esperado):
    assert faixa_frequencia(valor) == esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [(23.999, 4), (24, 3), (167.999, 3), (168, 2), (719.999, 2), (720, 1), (None, None)],
)
def test_faixa_lead_time_limites(valor, esperado):
    assert faixa_lead_time(valor) == esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [(0.15, 4), (0.15001, 3), (0.30, 3), (0.30001, 2), (0.45, 2), (0.45001, 1), (None, None)],
)
def test_faixa_cfr_limites_fechados(valor, esperado):
    assert faixa_cfr(valor) == esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [(0.999, 4), (1, 3), (23.999, 3), (24, 2), (167.999, 2), (168, 1), (None, None)],
)
def test_faixa_recuperacao_limites(valor, esperado):
    assert faixa_recuperacao(valor) == esperado


def test_classificacao_geral_exemplo_e_mediana_fracionaria():
    assert classificacao_geral([4, 3, 3, 1]) == 3
    assert classificacao_geral([4, 3, 2, 1]) == 2


def test_classificacao_geral_ignora_ausentes_e_exige_duas_notas():
    assert classificacao_geral([None, 4, None, 3]) == 3
    assert classificacao_geral([None, 4]) is None
    assert classificacao_geral([]) is None

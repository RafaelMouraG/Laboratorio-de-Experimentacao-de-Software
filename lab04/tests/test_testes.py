import numpy as np
import pytest
from scipy import stats

from lab04.simulacao import exemplo
from lab04.simulacao.gerador import gerar
from lab04.simulacao.testes import (
    ALTERNATIVA,
    METODO_MW,
    delta_cliff,
    g_hedges,
    mann_whitney,
    welch,
)


@pytest.fixture
def conjuntos():
    return gerar(np.random.default_rng(42), (30, 25), 1.5, 2.1, efeito=0.8, repeticoes=50)


def test_welch_vetorizado_bate_com_o_scipy_um_conjunto_por_vez(conjuntos):
    com, sem = conjuntos
    r = welch(com, sem)
    assert r.p.shape == (50,)
    for i in range(len(com)):
        esperado = stats.ttest_ind(com[i], sem[i], equal_var=False)
        assert r.estatistica[i] == pytest.approx(esperado.statistic, rel=1e-12)
        assert r.p[i] == pytest.approx(esperado.pvalue, rel=1e-12)


def test_mann_whitney_vetorizado_bate_com_o_scipy_um_conjunto_por_vez(conjuntos):
    com, sem = conjuntos
    r = mann_whitney(com, sem)
    assert r.p.shape == (50,)
    for i in range(len(com)):
        esperado = stats.mannwhitneyu(com[i], sem[i], alternative="two-sided", method="asymptotic")
        assert r.estatistica[i] == esperado.statistic
        assert r.p[i] == pytest.approx(esperado.pvalue, rel=1e-12)


def test_escolhas_do_mann_whitney_ficam_registradas():
    assert ALTERNATIVA == "two-sided"
    assert METODO_MW == "asymptotic"


def test_axis_zero_da_o_mesmo_que_axis_menos_um(conjuntos):
    com, sem = conjuntos
    np.testing.assert_allclose(welch(com.T, sem.T, axis=0).p, welch(com, sem).p)
    np.testing.assert_allclose(mann_whitney(com.T, sem.T, axis=0).p, mann_whitney(com, sem).p)
    np.testing.assert_allclose(g_hedges(com.T, sem.T, axis=0), g_hedges(com, sem))
    np.testing.assert_allclose(delta_cliff(com.T, sem.T, axis=0), delta_cliff(com, sem))


def test_mudar_a_escala_nao_muda_os_p_valores():
    a = gerar(np.random.default_rng(3), 30, 0.0, 2.0, efeito=0.5, repeticoes=20)
    b = gerar(np.random.default_rng(3), 30, 4.0, 2.0, efeito=0.5, repeticoes=20)
    np.testing.assert_allclose(welch(*a).p, welch(*b).p, rtol=1e-9)
    np.testing.assert_array_equal(mann_whitney(*a).p, mann_whitney(*b).p)


def test_g_de_hedges_confere_com_a_conta_na_mao():
    x, y = np.array([3.0, 5.0, 7.0, 9.0]), np.array([1.0, 2.0, 3.0])
    sp = np.sqrt((3 * np.var(x, ddof=1) + 2 * np.var(y, ddof=1)) / 5)
    j = 1 - 3 / (4 * 7 - 9)
    assert g_hedges(x, y) == pytest.approx((6 - 2) / sp * j)
    assert g_hedges(y, x) == pytest.approx(-(6 - 2) / sp * j)


def test_delta_de_cliff_confere_com_todos_os_pares(conjuntos):
    com, sem = conjuntos
    pares = np.sign(com[:, :, None] - sem[:, None, :]).mean(axis=(1, 2))
    np.testing.assert_allclose(delta_cliff(com, sem), pares)


def test_delta_de_cliff_com_empates_e_extremos():
    assert delta_cliff([1.0, 2.0], [1.0, 2.0]) == pytest.approx(0.0)
    assert delta_cliff([5.0, 6.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)
    assert delta_cliff([1.0, 2.0], [5.0, 6.0]) == pytest.approx(-1.0)
    assert delta_cliff([2.0], [1.0, 2.0]) == pytest.approx(0.5)


def test_exemplo_reproduz_os_mesmos_numeros():
    assert exemplo.tabela(exemplo.rodar()) == exemplo.tabela(exemplo.rodar())


def test_exemplo_do_readme_esta_atualizado():
    texto = exemplo.README.read_text(encoding="utf-8")
    bloco = texto.split(exemplo.INICIO, 1)[1].split(exemplo.FIM, 1)[0].strip()
    assert bloco == exemplo.tabela(exemplo.rodar())

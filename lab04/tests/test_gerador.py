import math

import numpy as np
import pytest

from lab04.simulacao.gerador import Cenario, cenario_base, efeito_observado, gerar
from lab04.simulacao.parametros import Parametros


def _rng():
    return np.random.default_rng(42)


def test_mesma_semente_da_os_mesmos_dados():
    a = gerar(_rng(), 30, 1.5, 2.0, efeito=0.7, repeticoes=100)
    b = gerar(_rng(), 30, 1.5, 2.0, efeito=0.7, repeticoes=100)
    np.testing.assert_array_equal(a[0], b[0])
    np.testing.assert_array_equal(a[1], b[1])


def test_devolve_uma_linha_por_conjunto():
    com, sem = gerar(_rng(), (30, 10), 1.5, (2.0, 1.0), repeticoes=7)
    assert com.shape == (7, 30) and sem.shape == (7, 10)
    assert (com > 0).all() and (sem > 0).all()


def test_efeito_zero_mantem_as_medianas_proximas():
    com, sem = gerar(_rng(), 30, math.log(4.5), 2.0, efeito=0.0, repeticoes=2000)
    med_com, med_sem = np.median(com), np.median(sem)
    assert med_com == pytest.approx(med_sem, rel=0.05)
    assert med_sem == pytest.approx(4.5, rel=0.05)


@pytest.mark.parametrize("efeito", [0.5, 1.56])
def test_efeito_positivo_multiplica_a_mediana_por_exp_do_efeito(efeito):
    com, sem = gerar(_rng(), 30, math.log(4.5), 2.0, efeito=efeito, repeticoes=2000)
    assert np.median(com) / np.median(sem) == pytest.approx(math.exp(efeito), rel=0.05)


def test_sigma_diferente_por_grupo():
    com, sem = gerar(_rng(), 30, 0.0, (2.0, 0.5), repeticoes=2000)
    assert np.log(com).std(ddof=1) == pytest.approx(2.0, rel=0.02)
    assert np.log(sem).std(ddof=1) == pytest.approx(0.5, rel=0.02)


@pytest.mark.parametrize("n, sigma", [(1, 1.0), (30, 0.0), (30, (1.0, -1.0))])
def test_recusa_parametros_invalidos(n, sigma):
    with pytest.raises(ValueError):
        gerar(_rng(), n, 0.0, sigma)


def test_cenario_base_usa_sigma_comum_e_mu_do_grupo_sem_bot():
    p = {
        "com_bot": Parametros("com_bot", 30, 36.8, 3.0, 2.4, 0.03),
        "sem_bot": Parametros("sem_bot", 28, 3.0, 1.5, 1.8, 0.02),
    }
    c = cenario_base(p)
    assert isinstance(c, Cenario)
    assert c.n == (30, 28) and c.mu == 1.5
    assert c.sigma == pytest.approx((2.1, 2.1))
    assert efeito_observado(p) == pytest.approx(1.5)

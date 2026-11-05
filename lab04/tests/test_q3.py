import math

import numpy as np
import pytest

from lab04.simulacao import motor, parametros, q2, q3
from lab04.simulacao.gerador import Cenario, cenario_base, contaminar


@pytest.fixture(scope="module")
def p():
    return parametros.calcular()


@pytest.fixture(scope="module")
def resultado():
    return q3.rodar()


def test_contaminar_multiplica_a_fracao_pedida():
    x = np.ones((200, 500))
    y = contaminar(np.random.default_rng(42), x, 0.05, 50.0)
    assert set(np.unique(y)) == {1.0, 50.0}
    assert (y == 50.0).mean() == pytest.approx(0.05, abs=0.003)


def test_contaminar_com_fracao_zero_nao_muda_nada():
    x = np.random.default_rng(1).lognormal(size=(3, 10))
    np.testing.assert_array_equal(contaminar(np.random.default_rng(2), x, 0.0, 50.0), x)


@pytest.mark.parametrize("fracao, fator", [(-0.1, 2.0), (1.0, 2.0), (0.1, 0.0)])
def test_contaminar_recusa_parametros_invalidos(fracao, fator):
    with pytest.raises(ValueError):
        contaminar(np.random.default_rng(0), np.ones(5), fracao, fator)


def test_cada_situacao_muda_uma_coisa_do_base(p):
    base = cenario_base(p)
    s = q3.situacoes(p)
    assert set(s) == {"assimetria", "outliers", "n_pequeno", "dispersoes"}
    assert s["assimetria"] == Cenario(base.n, base.mu, tuple(q3.FATOR_SIGMA * x for x in base.sigma))
    assert s["outliers"] == Cenario(base.n, base.mu, base.sigma, q3.FRACAO_OUTLIERS, q3.FATOR_OUTLIERS)
    assert s["n_pequeno"] == Cenario((10, 10), base.mu, base.sigma)
    assert s["dispersoes"].sigma == (p["com_bot"].sigma, p["sem_bot"].sigma)
    assert s["dispersoes"].sigma[0] != s["dispersoes"].sigma[1]


def test_efeito_que_iguala_as_medias(p):
    c = q3.situacoes(p)["dispersoes"]
    e = q3.efeito_medias_iguais(c)
    media_com = math.exp(c.mu + e + c.sigma[0] ** 2 / 2)
    media_sem = math.exp(c.mu + c.sigma[1] ** 2 / 2)
    assert media_com == pytest.approx(media_sem)


def test_todas_as_situacoes_nos_dois_alfas_e_em_toda_a_grade(resultado, p):
    for nome, c in q3.situacoes(p).items():
        g = resultado[resultado["situacao"] == nome]
        assert set(g["alfa"]) == set(motor.ALFAS)
        assert set(q2.EFEITOS) <= set(g["efeito"])
    disp = resultado[resultado["situacao"] == "dispersoes"]
    assert q3.efeito_medias_iguais(q3.situacoes(p)["dispersoes"]) in set(disp["efeito"])


def test_outliers_mudam_os_dados_do_motor(p):
    c = q3.situacoes(p)["outliers"]
    sem_outliers = Cenario(c.n, c.mu, c.sigma)
    a = motor.simular("x", c, efeito=math.log(5), n_rep=2000)
    b = motor.simular("x", sem_outliers, efeito=math.log(5), n_rep=2000)
    assert not a["rejeicoes"].equals(b["rejeicoes"])


def test_mann_whitney_segura_o_alfa_quando_sua_h0_e_verdadeira(resultado):
    zero = resultado[(resultado["efeito"] == 0.0) & (resultado["teste"] == "mann_whitney")]
    # Não passa de α além do sorteio. Pode ficar abaixo: com n = 10 a aproximação de U com correção
    # de continuidade é conservadora (cerca de 0,7% em α = 1%).
    for _, l in zero.iterrows():
        assert 0.6 * l.alfa <= l.proporcao <= l.alfa + 3 * motor.margem(l.alfa)


def test_csv_versionado_tem_a_q3_atualizada(resultado):
    csv = motor.ler().set_index(motor.CHAVE)
    for _, l in resultado.iterrows():
        assert csv.loc[(l.situacao, l.efeito, l.teste, l.alfa), "rejeicoes"] == l.rejeicoes


def test_tabelas_da_q3_no_readme_estao_atualizadas(resultado, p):
    texto = q3.README.read_text(encoding="utf-8")
    bloco = texto.split(q3.INICIO, 1)[1].split(q3.FIM, 1)[0].strip()
    assert bloco == q3.tabela(resultado, q2.rodar(), q3.situacoes(p))

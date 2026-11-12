import pytest

from lab04.simulacao import amostra_grande as ag, parametros
from lab04.simulacao.gerador import cenario_base


@pytest.fixture(scope="module")
def r():
    return ag.ler()


@pytest.fixture(scope="module")
def c():
    return cenario_base(parametros.calcular())


def test_csv_tem_toda_a_grade(r):
    assert r["n"].tolist() == list(ag.TAMANHOS)
    assert list(r.columns) == ag.COLUNAS
    assert (r["n_rep"] == ag.N_REP).all()


def test_medir_e_reprodutivel_e_bate_com_o_csv(r, c):
    assert ag.medir(c, 30) == ag.medir(c, 30)
    linha = r[r["n"] == 300].iloc[0]
    for coluna, valor in ag.medir(c, 300).items():
        assert linha[coluna] == pytest.approx(valor)


def test_p_valor_do_mann_whitney_cai_com_o_n(r):
    p = r["p_mann_whitney"].to_numpy()
    assert p[-1] < 1e-5 < 0.05 < p[0]
    assert r["rejeicao_mann_whitney"].iloc[-1] > 0.95


def test_efeito_nao_cresce_com_o_n(r, c):
    delta = ag.delta_verdadeiro(c)
    assert delta < 0.05
    assert (abs(r["delta_cliff"] - delta) < 0.01).all()
    assert (abs(r["g_hedges"]) < 0.05).all()
    assert r["diferenca_medianas_h"].iloc[-1] == pytest.approx(ag.diferenca_verdadeira_h(c), abs=5 / 60)


def test_efeito_e_de_minutos(c):
    assert 10 <= ag.diferenca_verdadeira_h(c) * 60 <= 60


def test_formato_do_p_valor():
    assert ag.p_valor(0.4512) == "0.451"
    assert ag.p_valor(9.04e-8) == "9.0 × 10^-8"


def test_ler_sem_algum_n_avisa(tmp_path, r):
    caminho = tmp_path / "amostra_grande.csv"
    r[r["n"] != 30_000].to_csv(caminho, index=False)
    with pytest.raises(ValueError, match="amostra_grande"):
        ag.ler(caminho)

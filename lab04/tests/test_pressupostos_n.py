import math

import pytest

from lab04.simulacao import motor, parametros, pressupostos_n as pn, q3
from lab04.simulacao.gerador import cenario_base


@pytest.fixture(scope="module")
def coletado():
    return cenario_base(parametros.calcular()).n[0]


@pytest.fixture(scope="module")
def curva():
    return pn.curva(motor.ler(), motor.ler(pn.SAIDA))


def test_efeito_da_grade_e_o_x3_da_q2_com_cerca_de_metade_de_poder():
    sim = motor.ler()
    assert any(math.isclose(e, pn.EFEITO) for e in sim["efeito"])
    base = sim[(sim["situacao"] == "base") & (sim["teste"] == "mann_whitney") & (sim["alfa"] == 0.05)
               & (sim["efeito"] == pn.EFEITO)]
    assert 0.4 <= (base["rejeicoes"] / base["n_rep"]).iloc[0] <= 0.6


def test_nao_simula_de_novo_o_que_ja_esta_na_q2_e_na_q3(coletado):
    extras = motor.ler(pn.SAIDA)
    pares = set(zip(extras["situacao"], extras["n"]))
    assert all(n != coletado for _, n in pares)
    assert ("base", q3.N_PEQUENO) not in pares
    assert pares == {(s, n) for s in pn.SITUACOES for n in pn.TAMANHOS if pn.origem(s, n, coletado) is None}


def test_sementes_novas_nao_colidem_com_as_do_simulacoes_csv():
    nomes = {pn.combinacao(s, n) for s in pn.SITUACOES for n in pn.TAMANHOS}
    assert nomes.isdisjoint(set(motor.ler()["situacao"]))


@pytest.mark.parametrize("situacao", pn.SITUACOES)
def test_n_coletado_e_n_10_do_base_sao_as_linhas_da_q3(curva, coletado, situacao):
    sim = motor.ler()
    pontos = [(coletado, situacao)] + ([(q3.N_PEQUENO, "n_pequeno")] if situacao == "base" else [])
    for n, fonte in pontos:
        q = sim[(sim["situacao"] == fonte) & sim["efeito"].isin(pn.EFEITOS)].sort_values(["efeito", "teste", "alfa"])
        c = curva[(curva["situacao"] == situacao) & (curva["n"] == n)].sort_values(["efeito", "teste", "alfa"])
        assert c["rejeicoes"].tolist() == q["rejeicoes"].tolist()


def test_mann_whitney_segura_o_alfa_em_todo_n(curva):
    zero = curva[(curva["teste"] == "mann_whitney") & (curva["efeito"] == 0.0)]
    for _, l in zero.iterrows():
        # Faixa larga: n = 10 com a aproximação normal de U já fica em 4,3% na Q3.
        assert abs(l["proporcao"] - l["alfa"]) <= 3 * motor.margem(l["alfa"]) + 0.005


def test_vantagem_tem_uma_linha_por_situacao_e_n(curva):
    v = pn.vantagem(curva)
    assert len(v) == len(pn.SITUACOES) * len(pn.TAMANHOS)
    assert (v["diferenca"] == v["mann_whitney"] - v["welch"]).all()


def test_curva_sem_as_linhas_novas_avisa():
    extras = motor.ler(pn.SAIDA)
    with pytest.raises(ValueError, match="pressupostos_n"):
        pn.curva(motor.ler(), extras[extras["n"] != 200])


def test_tabela_segue_a_ordem_da_q3(curva):
    linhas = [l for l in pn.tabela(curva).splitlines() if l.startswith("| `")]
    assert [l.split("`")[1] for l in linhas[:: len(pn.TAMANHOS)]] == list(pn.SITUACOES)

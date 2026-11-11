import math

import pandas as pd
import pytest

from lab04.simulacao import motor, parametros, q4
from lab04.simulacao.gerador import cenario_base, efeito_observado


@pytest.fixture(scope="module")
def p():
    return parametros.calcular()


@pytest.fixture(scope="module")
def curva():
    return q4.curva(motor.ler())


def test_nao_simula_de_novo_o_n_coletado(p):
    coletado = cenario_base(p).n[0]
    situacoes = set(q4.rodar()["situacao"])
    assert q4.situacao(coletado) not in situacoes
    assert situacoes == {q4.situacao(n) for n in q4.TAMANHOS if n != coletado}


def test_todo_n_da_grade_esta_no_csv_e_roda_no_efeito_observado(p):
    sim = motor.ler()
    amostra = sim[sim["situacao"].str.startswith(q4.PREFIXO)]
    assert not amostra.empty
    assert amostra["efeito"].map(lambda e: math.isclose(e, efeito_observado(p))).all()


def test_n_coletado_e_a_linha_do_cenario_base(p, curva):
    coletado = cenario_base(p).n[0]
    sim = motor.ler()
    base = sim[(sim["situacao"] == "base") & sim["efeito"].map(lambda e: math.isclose(e, efeito_observado(p)))]
    linha = curva[curva["n"] == coletado].sort_values(["teste", "alfa"])
    assert linha["rejeicoes"].tolist() == base.sort_values(["teste", "alfa"])["rejeicoes"].tolist()


def test_poder_cresce_com_o_n(curva):
    for (_, _), g in curva.groupby(["teste", "alfa"]):
        poder = g.sort_values("n")["proporcao"].to_numpy()
        # Ruído de 10.000 repetições perto de 100% pode inverter a ordem por poucas rejeições.
        assert (poder[1:] >= poder[:-1] - 0.01).all()


def test_mann_whitney_precisa_de_menos_prs_que_o_welch(curva):
    n_m, n_w = q4.n_para(curva, "mann_whitney"), q4.n_para(curva, "welch")
    assert n_m is not None and n_w is not None
    assert n_m < n_w


def _curva(poderes, ns=(10, 20, 30)):
    return pd.DataFrame({"teste": "t", "alfa": 0.05, "n": ns[: len(poderes)], "proporcao": poderes})


def test_n_para_interpola_e_arredonda_para_cima():
    assert q4.n_para(_curva([0.5, 0.7, 0.9]), "t") == 25
    assert q4.n_para(_curva([0.5, 0.79, 0.81]), "t") == 25


def test_n_para_sem_chegar_ao_alvo_devolve_none():
    assert q4.n_para(_curva([0.1, 0.2, 0.3]), "t") is None


def test_n_para_ja_no_primeiro_ponto():
    assert q4.n_para(_curva([0.85, 0.9, 0.95]), "t") == 10


def test_curva_sem_as_linhas_da_q4_avisa(tmp_path):
    sim = motor.ler()
    with pytest.raises(ValueError, match="Q4"):
        q4.curva(sim[~sim["situacao"].str.startswith(q4.PREFIXO)])

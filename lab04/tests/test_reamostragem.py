import math

import numpy as np
import pandas as pd
import pytest

from lab04.simulacao import motor, parametros, q2, reamostragem
from lab04.simulacao.gerador import cenario_base, efeito_observado


@pytest.fixture(scope="module")
def forma():
    return reamostragem.residuos()


def test_residuos_tem_media_zero_em_cada_grupo(forma):
    prs = pd.read_csv(parametros.CSV)
    assert len(forma) == len(prs)
    for grupo in ("com_bot", "sem_bot"):
        assert forma[(prs["grupo"] == grupo).to_numpy()].mean() == pytest.approx(0, abs=1e-12)


def test_gerar_so_devolve_tempos_que_existem_na_forma(forma):
    com, sem = reamostragem.gerar(np.random.default_rng(0), forma, (30, 20), mu=1.0, efeito=0.5, repeticoes=50)
    assert com.shape == (50, 30) and sem.shape == (50, 20)
    assert np.isin(np.round(np.log(sem) - 1.0, 9), np.round(forma, 9)).all()
    assert np.isin(np.round(np.log(com) - 1.5, 9), np.round(forma, 9)).all()


def test_efeito_zero_da_a_mesma_distribuicao_nos_dois_grupos(forma):
    com, sem = reamostragem.gerar(np.random.default_rng(1), forma, (30, 30), mu=1.0, repeticoes=20_000)
    # A mediana não serve aqui: o log é bimodal, com um vão bem no meio da distribuição.
    assert np.log(com).mean() == pytest.approx(np.log(sem).mean(), abs=0.02)
    assert np.log(com).std() == pytest.approx(np.log(sem).std(), rel=0.01)
    assert com.max() == sem.max()  # com 600 mil sorteios, os dois grupos tiram o maior resíduo


def test_csv_tem_a_mesma_grade_do_cenario_base():
    sim = motor.ler()
    p = parametros.calcular()
    esperados = sorted({*q2.EFEITOS, efeito_observado(p)})
    linhas = sim[sim["situacao"] == reamostragem.SITUACAO]
    assert sorted(linhas["efeito"].unique()) == pytest.approx(esperados)
    assert len(linhas) == len(esperados) * len(motor.TESTES) * len(motor.ALFAS)


def test_csv_bate_com_uma_nova_rodada_no_efeito_zero(forma):
    base = cenario_base(parametros.calcular())
    novo = reamostragem.simular(forma, base.n, base.mu, 0.0)
    sim = motor.ler()
    antigo = sim[(sim["situacao"] == reamostragem.SITUACAO) & (sim["efeito"] == 0.0)]
    chave = ["teste", "alfa"]
    assert novo.sort_values(chave)["rejeicoes"].tolist() == antigo.sort_values(chave)["rejeicoes"].tolist()


def test_sem_a_cauda_da_lognormal_o_welch_segura_o_alfa_e_tem_poder():
    sim = motor.ler()
    efeito = efeito_observado(parametros.calcular())

    def taxa(situacao, e):
        l = sim[(sim["situacao"] == situacao) & (sim["teste"] == "welch") & (sim["alfa"] == 0.05)
                & sim["efeito"].map(lambda x: math.isclose(x, e, abs_tol=1e-12))].iloc[0]
        return l["rejeicoes"] / l["n_rep"]

    assert taxa(reamostragem.SITUACAO, 0.0) > 2 * taxa("base", 0.0)
    assert taxa(reamostragem.SITUACAO, 0.0) < 0.05 + motor.margem(0.05)
    assert taxa(reamostragem.SITUACAO, efeito) > 2 * taxa("base", efeito)


def test_cauda_da_lognormal_passa_da_real_no_grupo_com_bot():
    c = reamostragem.cauda()["com_bot"]
    assert c["media_lognormal"] > 2 * c["media_real"]
    assert c["p99_lognormal"] > c["maximo_real"]

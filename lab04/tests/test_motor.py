import numpy as np
import pandas as pd
import pytest

from lab04.simulacao import motor, q1
from lab04.simulacao.gerador import Cenario

CENARIO = Cenario(n=(30, 30), mu=1.5, sigma=(2.1, 2.1))


def test_dados_normais_com_h0_verdadeira_ficam_perto_de_5_por_cento():
    rng = np.random.default_rng(42)
    com = rng.normal(10.0, 2.0, size=(motor.N_REP, 30))
    sem = rng.normal(10.0, 2.0, size=(motor.N_REP, 30))
    r = motor.rejeicoes(com, sem, alfas=(0.05,))
    folga = 3 * motor.margem(0.05)
    for teste in motor.TESTES:
        assert r[teste, 0.05] / motor.N_REP == pytest.approx(0.05, abs=folga)


def test_rejeicoes_contam_por_teste_e_por_alfa():
    rng = np.random.default_rng(1)
    com = rng.normal(0.0, 1.0, size=(500, 20))
    sem = rng.normal(0.0, 1.0, size=(500, 20))
    r = motor.rejeicoes(com, sem)
    assert set(r) == {(t, a) for t in motor.TESTES for a in motor.ALFAS}
    for t in motor.TESTES:
        assert r[t, 0.01] <= r[t, 0.05]


def test_efeito_grande_e_rejeitado_quase_sempre():
    # σ pequeno: com o σ real o Welch perde poder, e é isso que a Q2 mede.
    r = motor.simular("teste", Cenario(n=(30, 30), mu=1.5, sigma=(0.5, 0.5)), efeito=1.0, n_rep=500)
    assert (r["proporcao"] > 0.9).all()


def test_simular_devolve_o_formato_longo_do_csv():
    r = motor.simular("teste", CENARIO, efeito=0.5, n_rep=200)
    assert list(r.columns) == motor.COLUNAS + ["proporcao"]
    assert len(r) == len(motor.TESTES) * len(motor.ALFAS)
    assert (r["n_rep"] == 200).all() and (r["situacao"] == "teste").all()
    assert (r["proporcao"] == r["rejeicoes"] / 200).all()


def test_mesma_combinacao_da_o_mesmo_resultado():
    a = motor.simular("teste", CENARIO, efeito=0.5, n_rep=300)
    b = motor.simular("teste", CENARIO, efeito=0.5, n_rep=300)
    pd.testing.assert_frame_equal(a, b)


def test_semente_depende_so_da_combinacao():
    a = motor.gerador("base", 0.0).random(5)
    motor.gerador("outra", 0.0).random(5)
    np.testing.assert_array_equal(a, motor.gerador("base", 0.0).random(5))
    assert not np.array_equal(a, motor.gerador("base", 0.1).random(5))
    assert not np.array_equal(a, motor.gerador("outra", 0.0).random(5))
    assert not np.array_equal(a, motor.gerador("base", 0.0, semente=7).random(5))


def test_margem_com_10000_repeticoes():
    assert motor.margem(0.05) == pytest.approx(0.00427, abs=1e-5)
    assert motor.margem(0.01) == pytest.approx(0.00195, abs=1e-5)


def test_gravar_troca_so_as_combinacoes_que_rodaram(tmp_path):
    caminho = tmp_path / "saida" / "simulacoes.csv"
    a = motor.simular("a", CENARIO, efeito=0.0, n_rep=100)
    b = motor.simular("b", CENARIO, efeito=0.0, n_rep=100)
    motor.gravar(a, caminho)
    motor.gravar(b, caminho)
    a2 = motor.simular("a", CENARIO, efeito=0.0, n_rep=200)
    gravado = motor.gravar(a2, caminho)
    assert list(motor.ler(caminho).columns) == motor.COLUNAS
    assert len(gravado) == 2 * len(a)
    assert (gravado.loc[gravado["situacao"] == "a", "n_rep"] == 200).all()
    assert (gravado.loc[gravado["situacao"] == "b", "n_rep"] == 100).all()


def test_csv_versionado_tem_a_q1_atualizada():
    csv = motor.ler()
    base = csv[(csv["situacao"] == q1.SITUACAO) & (csv["efeito"] == 0.0)].set_index(["teste", "alfa"])
    for _, l in q1.rodar().iterrows():
        assert base.loc[(l.teste, l.alfa), "rejeicoes"] == l.rejeicoes


def test_tabela_da_q1_no_readme_esta_atualizada():
    texto = q1.README.read_text(encoding="utf-8")
    bloco = texto.split(q1.INICIO, 1)[1].split(q1.FIM, 1)[0].strip()
    assert bloco == q1.tabela(q1.rodar())


def test_gravar_de_novo_com_efeito_irracional_nao_duplica(tmp_path):
    caminho = tmp_path / "simulacoes.csv"
    r = motor.simular("a", CENARIO, efeito=0.22314355131420976, n_rep=100)
    motor.gravar(r, caminho)
    assert len(motor.gravar(r, caminho)) == len(r)
    assert set(motor.ler(caminho)["efeito"]) == {0.22314355131420976}

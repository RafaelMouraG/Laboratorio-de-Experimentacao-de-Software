import math

import pandas as pd

from lab03.analise.rq07 import carregar_combinacoes, comparar, transicao

REPOS = ["a", "b", "c", "d", "e", "f"]


def serie(valores):
    return pd.Series(valores, index=REPOS[: len(valores)], dtype="Float64")


def test_classificacoes_iguais_dao_zero_por_cento_e_kappa_um():
    c = serie([4, 3, 2, 1, 3, 2])
    resultado = comparar(c, c)
    assert resultado["n"] == 6 and resultado["mudaram"] == 0
    assert resultado["pct_mudaram"] == 0 and resultado["kappa"] == 1


def test_uma_categoria_so_e_iguais_tambem_da_kappa_um():
    assert comparar(serie([3, 3, 3]), serie([3, 3, 3]))["kappa"] == 1


def test_elite_para_low_baixa_mais_o_kappa_que_elite_para_high():
    base = serie([4, 3, 2, 1, 3, 2])
    para_high = serie([3, 3, 2, 1, 3, 2])
    para_low = serie([1, 3, 2, 1, 3, 2])
    perto, longe = comparar(base, para_high), comparar(base, para_low)
    assert perto["mudaram"] == longe["mudaram"] == 1
    assert math.isclose(perto["pct_mudaram"], 100 / 6)
    assert longe["kappa"] < perto["kappa"] < 1


def test_repo_sem_classificacao_numa_das_duas_fica_de_fora():
    a = serie([4, 3, 2, 1, 3, 2])
    b = serie([4, 3, 2, 1, 3, None])
    resultado = comparar(a, b)
    assert resultado["n"] == 5 and resultado["mudaram"] == 0


def test_transicao_conta_de_elite_para_low():
    matriz = transicao(serie([4, 4, 1]), serie([3, 4, 1]))
    assert list(matriz.index) == [4, 3, 2, 1]
    assert matriz.loc[4, 3] == 1 and matriz.loc[4, 4] == 1 and matriz.loc[1, 1] == 1
    assert matriz.to_numpy().sum() == 3


def test_c2_usa_lead_time_b_e_cfr_b_e_c3_usa_cfr_a(tmp_path):
    dados, saida = tmp_path / "dados", tmp_path / "saida"
    dados.mkdir(), saida.mkdir()
    pd.DataFrame({"repo": ["r"], "faixa_releases": [2], "faixa_lead_time_release": [2], "faixa_cfr_ci": [4],
                  "faixa_recuperacao": [3], "classificacao_geral": [2]}).to_csv(saida / "classificacao_c1.csv", index=False)
    pd.DataFrame({"repo": ["r"], "faixa_lead_time_commit": [3], "faixa_cfr_ci": [4],
                  "faixa_cfr_entrega": [1]}).to_csv(dados / "metricas.csv", index=False)
    alternativa = {"repo": ["r"], "faixa_frequencia": [3], "faixa_lead_time_commit": [3], "faixa_cfr_entrega": [1]}
    pd.DataFrame(alternativa).to_csv(dados / "metricas_c2.csv", index=False)
    pd.DataFrame(alternativa).to_csv(dados / "metricas_c3.csv", index=False)
    tabela = carregar_combinacoes(dados, saida)
    assert tabela.loc["r", "C2"] == 3  # mediana de 3, 3 e CFR (b) 1
    assert tabela.loc["r", "C3"] == 3  # mediana de 3, 3 e CFR (a) 4


def test_sem_metricas_c3_a_c3_fica_de_fora(tmp_path):
    dados, saida = tmp_path / "dados", tmp_path / "saida"
    dados.mkdir(), saida.mkdir()
    pd.DataFrame({"repo": ["r"], "faixa_releases": [2], "faixa_lead_time_release": [2], "faixa_cfr_ci": [4],
                  "faixa_recuperacao": [3], "classificacao_geral": [2]}).to_csv(saida / "classificacao_c1.csv", index=False)
    pd.DataFrame({"repo": ["r"], "faixa_lead_time_commit": [3], "faixa_cfr_ci": [4],
                  "faixa_cfr_entrega": [1]}).to_csv(dados / "metricas.csv", index=False)
    assert "C3" not in carregar_combinacoes(dados, saida)

import pandas as pd

from lab03.analise.classificacao_c1 import (
    contagem_notas,
    dados_c1,
    distribuicao_geral,
    tabela_cruzada,
)


def dados_exemplo():
    return pd.DataFrame({
        "repo": ["elite", "high", "low", "sem-classificacao", "duas-notas-c1"],
        "faixa_releases": [4, 3, 1, 1, 1],
        "faixa_lead_time_release": [4, 2, 1, None, 2],
        "faixa_cfr_ci": [4, 4, 3, None, None],
        "faixa_recuperacao": [3, None, 4, 2, None],
        "classificacao_geral": [4, 3, 1, None, 1],
    })


def test_dados_c1_exporta_repo_quatro_notas_e_geral():
    resultado = dados_c1(dados_exemplo())
    assert resultado.columns.tolist() == [
        "repo",
        "faixa_releases",
        "faixa_lead_time_release",
        "faixa_cfr_ci",
        "faixa_recuperacao",
        "classificacao_geral",
    ]
    assert len(resultado) == 5


def test_distribuicao_geral_inclui_percentual_sem_classificacao():
    resultado = distribuicao_geral(dados_exemplo()).set_index("classificacao_geral")
    assert resultado.loc["Elite", ["repositorios", "percentual"]].tolist() == [1, 20.0]
    assert resultado.loc["Low", ["repositorios", "percentual"]].tolist() == [2, 40.0]
    assert resultado.loc["Sem classificação", ["repositorios", "percentual"]].tolist() == [1, 20.0]


def test_contagem_notas_distingue_quatro_metricas_de_componentes_c1():
    resultado = contagem_notas(dados_exemplo()).set_index(["escopo", "notas_validas"])
    assert resultado.loc[("quatro_metricas", 4), "repositorios"] == 2
    assert resultado.loc[("quatro_metricas", 3), "repositorios"] == 1
    assert resultado.loc[("quatro_metricas", 2), "repositorios"] == 2
    assert resultado.loc[("componentes_c1", 3), "repositorios"] == 3
    assert resultado.loc[("componentes_c1", 2), "repositorios"] == 1
    assert resultado.loc[("componentes_c1", 1), "sem_classificacao"] == 1


def test_tabela_cruzada_inclui_faixas_ausentes_e_categoria_sem_classificacao():
    resultado = tabela_cruzada(dados_exemplo())
    faltante = resultado[
        (resultado["metrica"] == "Lead time (a)")
        & (resultado["faixa"] == "Sem nota")
        & (resultado["classificacao_geral"] == "Sem classificação")
    ].iloc[0]
    assert faltante["repositorios"] == 1
    assert faltante["percentual_na_categoria_geral"] == 100

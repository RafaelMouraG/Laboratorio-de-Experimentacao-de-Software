import matplotlib.pyplot as plt
import pandas as pd
import pytest

from lab03.analise import rq09
from lab03.analise.rq09 import (
    FATOR_ADOCAO,
    FERRAMENTAS_IA,
    LLM,
    PROGRAMACAO,
    com_c1_a_c4,
    deltas,
    fator_rq06,
    ferramentas_ia,
    figura,
    por_nivel,
    preparar,
    robustez,
    spearman,
)

LINGUAGENS = ["Python", "Go", "Rust", "TypeScript"]


def base(n_nenhuma=12, n_adotantes=36):
    """Repositórios sintéticos: releases por semana crescem com a %, e quem não adotou tem menos."""
    linhas = []
    for i in range(n_nenhuma):
        linhas.append({"repo": f"sem/{i}", "commits_ia": 0, "proporcao_ia_desde_adocao": None,
                       "arquivo_agente": False, "releases_por_semana": 0.1 + i / 1000})
    for i in range(n_adotantes):
        ia = i + 1
        linhas.append({"repo": f"ia/{i}", "commits_ia": ia, "proporcao_ia_desde_adocao": ia / 100,
                       "arquivo_agente": i % 2 == 0, "releases_por_semana": 1 + i / 10})
    df = pd.DataFrame(linhas)
    k = len(df)
    df["lead_time_release_horas"] = [100 - j for j in range(k)]
    df["cfr_ci"] = [(j * 7 % 11) / 20 for j in range(k)]
    df["recuperacao_mediana_horas"] = [(j * 5 % 13) + 1.0 for j in range(k)]
    df["estrelas"] = [1000 + j * 10 for j in range(k)]
    df["contribuidores"] = [10 + (j * 3 % k) for j in range(k)]
    df["idade_anos"] = [1 + (j * 7 % k) / 10 for j in range(k)]
    df["linguagem"] = [LINGUAGENS[j % 4] for j in range(k)]
    return df


def test_preparar_tira_excluidos_e_poe_grupos_em_ordem():
    df = base()
    excluido = pd.DataFrame([{**df.iloc[-1].to_dict(), "repo": "poucos/1", "commits_ia": 1,
                              "proporcao_ia_desde_adocao": 1 / 5}])
    pronto = preparar(pd.concat([df, excluido], ignore_index=True))
    assert "poucos/1" not in set(pronto["repo"])
    assert list(pronto[FATOR_ADOCAO].cat.categories) == ["nenhuma", "baixa", "alta"]
    assert (pronto.loc[~pronto["adotante"], FATOR_ADOCAO] == "nenhuma").all()
    assert pronto.loc[pronto["repo"] == "ia/0", FATOR_ADOCAO].item() == "baixa"   # 1%
    assert pronto.loc[pronto["repo"] == "ia/4", FATOR_ADOCAO].item() == "alta"    # 5%


def test_spearman_por_recorte_com_holm():
    tabela = spearman(preparar(base()))
    assert len(tabela) == 8 and set(tabela["recorte"]) == {"classificados", "adotantes"}
    releases = tabela[tabela["y"] == "releases_por_semana"].set_index("recorte")
    assert releases.loc["adotantes", "rho"] == pytest.approx(1.0)
    assert releases.loc["classificados", "n"] == 48 and releases.loc["adotantes", "n"] == 36
    assert (tabela["p_holm"] >= tabela["p_valor"]).all()


def test_delta_positivo_quando_o_grupo_mais_adotante_tem_mais():
    df = pd.DataFrame({"g": ["nenhuma"] * 3 + ["baixa"] * 3 + ["alta"] * 3,
                       "m": [1, 2, 3, 4, 5, 6, 7, 8, 9]})
    resultado = deltas(df, "g", "m")
    assert resultado == {"delta_baixa_nenhuma": 1.0, "delta_alta_nenhuma": 1.0, "delta_alta_baixa": 1.0}


def test_delta_vazio_quando_falta_grupo():
    df = pd.DataFrame({"g": ["baixa", "alta"], "m": [1.0, 2.0]})
    assert pd.isna(deltas(df, "g", "m")["delta_alta_nenhuma"])


def test_por_nivel_tem_kruskal_deltas_e_medianas():
    tabela = por_nivel(preparar(base()), "C1")
    assert list(tabela["metrica"]) == list(rq09.METRICAS)
    releases = tabela.set_index("metrica").loc["releases_por_semana"]
    assert releases["delta_alta_nenhuma"] == 1.0 and releases["rho_niveis"] > 0
    assert releases["n_nenhuma"] == 12 and releases["n_baixa"] + releases["n_alta"] == 36
    assert releases["p_holm"] < 0.05


def test_c1_a_c4_uma_linha_por_classificacao_e_metrica():
    tabela = com_c1_a_c4(preparar(base()))
    assert len(tabela) == 16 and set(tabela["classificacao"]) == {"C1", "C2", "C3", "C4"}


def test_adocao_entra_no_mesmo_holm_da_rq06():
    df = base()
    df.loc[df["repo"] == "ia/0", "proporcao_ia_desde_adocao"] = 1 / 5   # 1 de 5: excluído
    testes, _ = fator_rq06(preparar(df, tirar_excluidos=False))
    assert len(testes) == 5 * 4
    assert set(testes["fator"]) == {*rq09.rq06.FATORES, FATOR_ADOCAO}
    n = testes.groupby("fator")["n"].min()
    assert n[FATOR_ADOCAO] == 47 and n["quartil_estrelas"] == 48


def test_robustez_tira_as_ferramentas_de_ia():
    df = base()
    programacao = next(r for r, (c, _) in FERRAMENTAS_IA.items() if c == PROGRAMACAO)
    llm = next(r for r, (c, _) in FERRAMENTAS_IA.items() if c == LLM)
    df.loc[df["repo"] == "ia/10", "repo"] = programacao
    df.loc[df["repo"] == "ia/11", "repo"] = llm
    tabela = robustez(preparar(df))
    repos = tabela.groupby("recorte")["repos"].first()
    assert list(repos.sort_values(ascending=False)) == [48, 47, 46]


def test_lista_de_ferramentas_sem_repetidos_e_com_motivo():
    tabela = ferramentas_ia()
    assert tabela["repo"].is_unique
    assert set(tabela["categoria"]) == {PROGRAMACAO, LLM}
    assert tabela["motivo"].str.len().gt(0).all()


def test_figura_tem_dois_paineis_por_metrica():
    df = preparar(base())
    fig = figura(df, spearman(df), por_nivel(df, "C1"))
    assert len(fig.axes) == 2 * len(rq09.METRICAS)
    plt.close(fig)

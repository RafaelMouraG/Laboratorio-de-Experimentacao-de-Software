import pandas as pd
import pytest

from lab03.analise.rq09_niveis import (
    classificar,
    com_rotulos,
    commits_desde_adocao,
    concordancia,
    distribuicao,
    funil,
    nivel_c1,
    nivel_c4,
)


def repos(linhas):
    """``linhas`` = (repo, commits com IA, commits depois da adoção, arquivo de agente)."""
    return pd.DataFrame([
        {"repo": r, "commits_ia": c, "proporcao_ia_desde_adocao": c / d if c else None, "arquivo_agente": a}
        for r, c, d, a in linhas
    ])


@pytest.mark.parametrize(("ia", "desde", "nivel"), [
    (0, 0, 0),
    (1, 101, 1),    # 0,99%
    (1, 100, 2),    # 1% exato
    (4, 81, 2),     # 4,94%
    (5, 100, 3),    # 5% exato
    (3, 60, 3),     # 5% exato com outro denominador
    (19, 96, 3),    # 19,79%
    (20, 100, 4),   # 20% exato
    (2, 10, 4),     # 20% exato com o mínimo de commits
    (10, 10, 4),    # 100%
])
def test_cortes_de_robbes_nos_valores_exatos(ia, desde, nivel):
    assert nivel_c1(ia, desde) == nivel


def test_cortes_exatos_passando_pela_proporcao_do_csv():
    tabela = classificar(repos([("a", 1, 100, False), ("b", 5, 100, False), ("c", 20, 100, False),
                                ("d", 7, 140, False), ("e", 1, 101, False)]))
    assert tabela.set_index("repo")["C1"].to_dict() == {"a": 2, "b": 3, "c": 4, "d": 3, "e": 1}


def test_commits_depois_da_adocao_pela_conta_inversa():
    assert commits_desde_adocao(7, 7 / 140) == 140
    assert commits_desde_adocao(1, 1 / 3) == 3
    assert commits_desde_adocao(0, float("nan")) == 0


def test_menos_de_dez_commits_depois_da_adocao_fica_fora():
    tabela = classificar(repos([("nove", 1, 9, True), ("dez", 1, 10, False), ("sem_ia", 0, 0, False)]))
    linha = tabela.set_index("repo")
    assert bool(linha.loc["nove", "excluido"]) and not bool(linha.loc["dez", "excluido"])
    for nome in ("C1", "C2", "C3", "C4", "C1_grupo"):
        assert pd.isna(linha.loc["nove", nome])
    assert linha.loc["dez", "C1"] == 3  # 1 de 10 = 10%, consistente
    assert linha.loc["sem_ia", "C1"] == 0 and not bool(linha.loc["sem_ia", "excluido"])
    etapas = funil(tabela).set_index("etapa")["repos"]
    assert etapas["excluídos: menos de 10 commits depois da adoção"] == 1
    assert etapas["classificados no total"] == 2


def test_c4_arquivo_vale_mesmo_sem_commit_com_ia():
    assert nivel_c4(0, False) == 0
    assert nivel_c4(3, False) == 1
    assert nivel_c4(3, True) == 2
    assert nivel_c4(0, True) == 2
    tabela = classificar(repos([("so_arquivo", 0, 0, True)])).iloc[0]
    assert tabela["C1"] == 0 and tabela["C4"] == 2


def amostra():
    # 12 adotantes com % de 1/100 a 12/100 e dois sem IA, um deles com arquivo
    linhas = [(f"r{i:02d}", i, 100, i % 2 == 0) for i in range(1, 13)]
    return repos(linhas + [("nada", 0, 0, False), ("arq", 0, 0, True)])


def test_tercis_e_quartis_entre_os_adotantes():
    tabela = classificar(amostra()).set_index("repo")
    assert tabela.loc[[f"r{i:02d}" for i in range(1, 13)], "C2"].tolist() == [1] * 4 + [2] * 4 + [3] * 4
    assert tabela.loc[[f"r{i:02d}" for i in range(1, 13)], "C3"].tolist() == [1] * 3 + [2] * 3 + [3] * 3 + [4] * 3
    assert tabela.loc["nada", "C2"] == tabela.loc["nada", "C3"] == 0


def test_empate_na_porcentagem_cai_no_mesmo_quantil():
    tabela = classificar(repos([("a", 1, 100, False), ("b", 5, 100, False), ("c", 5, 100, False),
                                ("d", 5, 100, False), ("e", 20, 100, False)])).set_index("repo")
    assert tabela.loc[["b", "c", "d"], "C3"].nunique() == 1
    assert tabela.loc["a", "C3"] == 1 and tabela.loc["e", "C3"] == 4


def test_agrupamento_em_nenhuma_baixa_alta():
    tabela = classificar(amostra()).set_index("repo")
    assert tabela.loc["r04", "C1"] == 2 and tabela.loc["r04", "C1_grupo"] == 1   # 4%: limitada, baixa
    assert tabela.loc["r05", "C1"] == 3 and tabela.loc["r05", "C1_grupo"] == 2   # 5%: consistente, alta
    assert tabela.loc["r05", "C2_grupo"] == 2   # 2º tercil já é alta
    assert tabela.loc["r06", "C3_grupo"] == 1   # 2º quartil é baixa
    assert tabela.loc["r01", "C4_grupo"] == 1 and tabela.loc["r02", "C4_grupo"] == 2
    rotulos = com_rotulos(tabela.reset_index()).set_index("repo")
    assert rotulos.loc["r05", "C1"] == "consistente" and rotulos.loc["r05", "C1_grupo"] == "alta"


def test_distribuicao_soma_os_classificados():
    tabela = classificar(amostra())
    contagem = distribuicao(tabela)
    for nome, grupo in contagem.groupby("classificacao"):
        assert grupo["repos"].sum() == 14, nome


def test_concordancia_tem_todos_os_pares_nos_dois_recortes():
    pares = concordancia(classificar(amostra()))
    todos = pares[pares["recorte"] == "todos"]
    assert len(todos) == 7 and set(todos["n"]) == {14}
    sem_ia = pares[(pares["recorte"] == "adotantes")]
    assert set(sem_ia["n"]) == {12}


def test_comparar_da_rq07_continua_com_as_faixas_dora_por_padrao():
    from lab03.analise.rq07 import comparar
    a = pd.Series([0, 1, 2], index=list("xyz"))
    b = pd.Series([0, 1, 1], index=list("xyz"))
    resultado = comparar(a, b, labels=[0, 1, 2])
    assert resultado["mudaram"] == 1 and 0 < resultado["kappa"] < 1

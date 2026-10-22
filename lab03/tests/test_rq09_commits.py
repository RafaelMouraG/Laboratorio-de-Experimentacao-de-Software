import math

import pandas as pd
import pytest

from lab03.analise.rq09_commits import (
    COM_IA,
    SEM_IA,
    agregar,
    cobertura,
    comparar,
    grupo_por_ferramenta,
    ligar_releases,
    ligar_runs,
    parear,
    tabela_commits,
)

FIM = "2025-11-18"


def commit(sha, data):
    return {"sha": sha, "data": data, "mensagem": ""}


def releases_feitas_a_mao():
    # v1.0.1 sai em 10/11 e a v1.0.2, corretiva pelas notas, dois dias depois: a v1.0.1 falhou.
    # A v1.0.2 sai a menos de 7 dias do fim da janela (18/11) e fica censurada.
    return [
        {"tag_name": "v1.0.0", "published_at": "2025-11-01T00:00:00Z", "commits": [], "body": ""},
        {"tag_name": "v1.0.1", "published_at": "2025-11-10T00:00:00Z", "body": "",
         "commits": [commit("a", "2025-11-08T00:00:00Z"), commit("b", "2025-11-09T12:00:00Z"),
                     commit("e", "2025-11-10T06:00:00Z")]},
        {"tag_name": "v1.0.2", "published_at": "2025-11-12T00:00:00Z", "body": "fix: bug no login",
         # `a` aparece de novo, como num compare que cruza linhas de versão
         "commits": [commit("a", "2025-11-08T00:00:00Z"), commit("c", "2025-11-11T00:00:00Z")]},
    ]


def runs_feitos_a_mao():
    return pd.DataFrame([
        {"head_sha": "a", "conclusion": "success"},
        # `b` falhou e foi rodado de novo com sucesso: dois runs
        {"head_sha": "b", "conclusion": "failure"},
        {"head_sha": "b", "conclusion": "success"},
        # `d` só tem run cancelado, que não entra na CFR (a)
        {"head_sha": "d", "conclusion": "cancelled"},
    ])


def tabela_feita_a_mao():
    commits = [commit(s, d) for s, d in [
        ("e", "2025-11-10T06:00:00Z"), ("d", "2025-11-13T00:00:00Z"), ("c", "2025-11-11T00:00:00Z"),
        ("b", "2025-11-09T12:00:00Z"), ("a", "2025-11-08T00:00:00Z"), ("z", "2025-11-07T00:00:00Z"),
    ]]
    return tabela_commits("dono/repo", commits, ligar_releases(releases_feitas_a_mao(), FIM),
                          ligar_runs(runs_feitos_a_mao()), {"b": "Claude", "d": "Claude;Copilot"}).set_index("sha")


def test_ligar_releases_primeira_release_vale():
    ligacao = ligar_releases(releases_feitas_a_mao(), FIM)
    assert ligacao["a"] == {"tag_name": "v1.0.1", "lead_time_horas": 48.0, "release_falhou": True}
    assert ligacao["b"]["lead_time_horas"] == 12.0
    assert ligacao["c"] == {"tag_name": "v1.0.2", "lead_time_horas": 24.0, "release_falhou": None}


def test_ligar_releases_lead_time_negativo_fica_vazio():
    assert ligar_releases(releases_feitas_a_mao(), FIM)["e"]["lead_time_horas"] is None


def test_ligar_runs_conta_os_runs_validos():
    por_sha = ligar_runs(runs_feitos_a_mao())
    assert por_sha.loc["a"].tolist() == [1, 0]
    assert por_sha.loc["b"].tolist() == [2, 1]
    assert "d" not in por_sha.index


def test_commit_com_um_run():
    linha = tabela_feita_a_mao().loc["a"]
    assert (linha["runs_validos"], linha["falhou_ci"]) == (1, 0.0)
    assert (linha["tag_name"], linha["lead_time_horas"], linha["release_falhou"]) == ("v1.0.1", 48.0, 1.0)


def test_commit_com_dois_runs_falhou_se_algum_falhou():
    linha = tabela_feita_a_mao().loc["b"]
    assert (linha["runs_validos"], linha["runs_falha"], linha["falhou_ci"]) == (2, 1, 1.0)


def test_commit_sem_run_fica_sem_falha_de_ci():
    tabela = tabela_feita_a_mao()
    assert tabela.loc["c", "runs_validos"] == 0 and math.isnan(tabela.loc["c", "falhou_ci"])
    # run cancelado não conta como run
    assert tabela.loc["d", "runs_validos"] == 0 and math.isnan(tabela.loc["d", "falhou_ci"])


def test_commit_fora_de_qualquer_release():
    linha = tabela_feita_a_mao().loc["d"]
    assert pd.isna(linha["tag_name"])
    assert math.isnan(linha["lead_time_horas"]) and math.isnan(linha["release_falhou"])


def test_release_censurada_fica_vazia():
    linha = tabela_feita_a_mao().loc["c"]
    assert linha["tag_name"] == "v1.0.2" and math.isnan(linha["release_falhou"])


def test_periodo_comeca_no_primeiro_commit_com_ia():
    tabela = tabela_feita_a_mao()
    assert tabela["com_ia"].to_dict() == {"e": False, "d": True, "c": False, "b": True, "a": False, "z": False}
    # o primeiro commit com IA é `b`, em 09/11 12h
    assert tabela["desde_adocao"].to_dict() == {"e": True, "d": True, "c": True, "b": True, "a": False, "z": False}


def test_repositorio_sem_ia_fica_fora_do_periodo():
    tabela = tabela_commits("dono/repo", [commit("a", "2025-11-08T00:00:00Z")], {}, ligar_runs(runs_feitos_a_mao()), {})
    assert not tabela["desde_adocao"].any()
    assert tabela.loc[0, "falhou_ci"] == 0.0


def test_grupo_por_ferramenta():
    tabela = tabela_feita_a_mao()
    assert grupo_por_ferramenta(tabela, "Copilot").to_dict() == {
        "e": SEM_IA, "d": COM_IA, "c": SEM_IA, "b": None, "a": SEM_IA, "z": SEM_IA}


def test_cobertura():
    linhas = cobertura(tabela_feita_a_mao().reset_index()).set_index("recorte")
    assert linhas.loc["janela"].to_dict() == {
        "commits": 6, "sem_run": 4, "com_dois_runs_ou_mais": 1, "sem_release": 2,
        "release_censurada": 1, "lead_time_negativo": 1,
    }
    assert linhas.loc["desde_adocao_com_ia", "commits"] == 2
    assert linhas.loc["desde_adocao_sem_ia", "commits"] == 2


def agregado_feito_a_mao():
    # r1 e r2: com IA pior que sem IA. r3 tem só 2 commits com IA e sai pelo mínimo.
    linhas = []
    for repo, com, sem, n_com in [("r1", 0.5, 0.1, 10), ("r2", 0.4, 0.2, 10), ("r3", 0.0, 0.9, 2)]:
        linhas.append({"repo": repo, "grupo": COM_IA, "falhou_ci": com, "n_ci": n_com})
        linhas.append({"repo": repo, "grupo": SEM_IA, "falhou_ci": sem, "n_ci": 10})
    return pd.DataFrame(linhas)


def test_parear_respeita_o_minimo():
    resultado = parear(agregado_feito_a_mao(), "falhou_ci", minimo=5)
    assert resultado["repos"] == 2
    assert resultado["efeito"] == 1.0
    assert resultado["mediana_com_ia"] == pytest.approx(0.45)
    assert resultado["mediana_sem_ia"] == pytest.approx(0.15)


def test_parear_sem_minimo_entra_todo_mundo():
    resultado = parear(agregado_feito_a_mao(), "falhou_ci", minimo=1)
    # diferenças 0,4, 0,2 e -0,9: postos 2, 1 e 3 -> (3 - 3) / 6 = 0
    assert resultado["repos"] == 3
    assert resultado["efeito"] == pytest.approx(0.0)


def test_parear_sem_pares_fica_vazio():
    resultado = parear(agregado_feito_a_mao(), "falhou_ci", minimo=50)
    assert resultado["repos"] == 0 and resultado["p_valor"] is None


def test_agregar_e_comparar_de_ponta_a_ponta():
    tabela = tabela_feita_a_mao().reset_index()
    periodo = tabela[tabela["desde_adocao"]]
    agregado = agregar(periodo, periodo["com_ia"].map({True: COM_IA, False: SEM_IA})).set_index("grupo")
    # com IA: b (falhou) e d (sem run); sem IA: c (sem run) e e (sem run)
    assert agregado.loc[COM_IA, ["commits", "n_ci", "falhou_ci"]].tolist() == [2, 1, 1.0]
    assert agregado.loc[SEM_IA, "n_ci"] == 0
    resultado = comparar(tabela, minimo=1)
    assert set(resultado["recorte"]) == {"todas", "Claude", "Copilot"}
    todas = resultado[resultado["recorte"] == "todas"].set_index("medida")
    # lead time: b (12 h) contra c (24 h); sem IA não tem nenhum commit com run válido
    assert todas.loc["lead_time_horas", ["repos", "mediana_com_ia", "mediana_sem_ia"]].tolist() == [1, 12.0, 24.0]
    assert todas.loc["falhou_ci", "repos"] == 0
    # release: b e e estão na v1.0.1, que falhou; a diferença zero não dá teste
    assert todas.loc["release_falhou", "repos"] == 1 and pd.isna(todas.loc["release_falhou", "p_valor"])

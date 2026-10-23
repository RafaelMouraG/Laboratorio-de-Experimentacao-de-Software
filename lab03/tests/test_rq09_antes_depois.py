import math

import pandas as pd
import pytest

from lab03.analise.rq09_antes_depois import (
    ANTES,
    DEPOIS,
    MINIMO_PARES,
    antes_depois,
    calcular,
    comparar,
    elegiveis,
    funil,
    inicio_run,
    mann_kendall,
    parear,
    por_trimestre,
    tendencias,
)

INICIO, FIM = "2025-10-01", "2026-09-30"
T0 = "2026-01-15T12:00:00Z"


def commit(data):
    return {"sha": data, "data": data, "mensagem": ""}


def releases_df(linhas):
    df = pd.DataFrame(linhas, columns=["tag_name", "published_at", "sem_anterior", "commits"])
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True)
    return df


def runs_df(linhas):
    df = pd.DataFrame(linhas, columns=["id", "workflow_id", "conclusion", "created_at", "run_started_at",
                                       "updated_at"])
    df["inicio"] = inicio_run(df)
    df["run_started_at"] = df["inicio"]
    df["updated_at"] = pd.to_datetime(df["updated_at"], utc=True)
    return df


def releases_feitas_a_mao():
    # A v1 sai 1 s antes do primeiro commit com IA e a v2 exatamente nele: v1 é "antes", v2 é "depois".
    return releases_df([
        ("v0", "2025-12-01T00:00:00Z", True, []),
        ("v1", "2026-01-15T11:59:59Z", False, [commit("2026-01-14T11:59:59Z")]),
        ("v2", T0, False, [commit("2026-01-15T10:00:00Z"), commit("2026-01-15T11:00:00Z")]),
        ("v3", "2026-03-01T00:00:00Z", False, [commit("2026-02-28T00:00:00Z")]),
    ])


def runs_feitos_a_mao():
    # workflow 1: falha antes de t0 e sucesso exatamente em t0. O episódio fica censurado no "antes"
    # e, no "depois", o sucesso não fecha nada.
    return runs_df([
        (1, 1, "success", "2026-01-10T00:00:00Z", None, "2026-01-10T00:10:00Z"),
        (2, 1, "failure", "2026-01-14T00:00:00Z", "2026-01-14T00:00:00Z", "2026-01-14T00:10:00Z"),
        (3, 1, "success", "2026-01-15T11:00:00Z", T0, "2026-01-15T13:00:00Z"),
        (4, 1, "failure", "2026-02-01T00:00:00Z", None, "2026-02-01T00:10:00Z"),
        (5, 1, "success", "2026-02-01T02:00:00Z", None, "2026-02-01T03:00:00Z"),
        (6, 1, "cancelled", "2026-02-02T00:00:00Z", None, "2026-02-02T00:10:00Z"),
    ])


def test_divide_no_instante_exato_do_primeiro_commit_com_ia():
    antes, depois = antes_depois("o/r", T0, releases_feitas_a_mao(), runs_feitos_a_mao(), INICIO, FIM)

    assert antes["periodo"] == ANTES and depois["periodo"] == DEPOIS
    assert (antes["releases"], depois["releases"]) == (2, 2)
    # o run 3 começou (run_started_at) exatamente em t0, apesar de criado antes
    assert (antes["runs_validos"], depois["runs_validos"]) == (2, 3)
    assert antes["cfr_ci"] == pytest.approx(1 / 2)
    assert depois["cfr_ci"] == pytest.approx(1 / 3)
    # 01/10 a 15/01 são 106 dias; 15/01 a 30/09, 258
    assert (antes["dias"], depois["dias"]) == (106, 258)
    assert antes["releases_por_semana"] == pytest.approx(2 / (106 / 7))
    assert depois["releases_por_semana"] == pytest.approx(2 / (258 / 7))


def test_lead_time_e_recuperacao_de_cada_lado():
    antes, depois = antes_depois("o/r", T0, releases_feitas_a_mao(), runs_feitos_a_mao(), INICIO, FIM)

    # v0 não tem anterior; v1 tem um commit de 24 h
    assert antes["lead_time_release_horas"] == pytest.approx(24)
    assert antes["lead_time_release_avaliadas"] == 1
    # v2: commits de 2 h e 1 h (a) = 2 h; v3: 24 h. Mediana de (2, 24) = 13; de (2, 1, 24) = 2
    assert depois["lead_time_release_horas"] == pytest.approx(13)
    assert depois["lead_time_commit_horas"] == pytest.approx(2)
    # o episódio aberto em 14/01 não fecha no "antes"
    assert antes["recuperacao_horas"] is None and antes["recuperacao_fechados"] == 0
    # falha em 01/02 00:00, sucesso atualizado 03:00
    assert depois["recuperacao_horas"] == pytest.approx(3)


def test_repositorio_criado_na_janela_conta_o_antes_desde_a_criacao():
    linhas = calcular(
        pd.DataFrame([{"repo": "o/r", "primeiro_commit_ia": T0, "criado_em": "2025-12-01T08:00:00Z"}]),
        releases_feitas_a_mao().assign(repo="o/r"), runs_feitos_a_mao().assign(repo="o/r"), INICIO, FIM,
    )[0]
    antes = linhas[linhas["periodo"] == ANTES].iloc[0]
    assert antes["dias"] == 45  # 01/12 a 15/01


def por_periodo_de(valores):
    """repo → (dias antes, dias depois, releases antes, releases depois, runs antes, runs depois, cfr antes, cfr depois)."""
    linhas = []
    for repo, (da, dd, ra, rd, na, nd, ca, cd) in valores.items():
        for periodo, dias, rel, runs, cfr in ((ANTES, da, ra, na, ca), (DEPOIS, dd, rd, nd, cd)):
            linhas.append({"repo": repo, "periodo": periodo, "dias": dias, "releases": rel, "runs_validos": runs,
                           "cfr_ci": cfr, "releases_por_semana": rel / (dias / 7),
                           "lead_time_release_horas": None, "lead_time_commit_horas": None,
                           "recuperacao_horas": None})
    return pd.DataFrame(linhas)


def test_repo_com_poucos_dados_de_um_lado_fica_fora_e_entra_no_funil():
    por_periodo = por_periodo_de({
        "ok/ok": (120, 200, 5, 5, 100, 100, 0.1, 0.2),
        "pouca/release": (120, 200, 2, 9, 100, 100, 0.1, 0.2),
        "poucos/runs": (120, 200, 5, 5, 29, 100, 0.1, 0.2),
        "cedo/demais": (30, 300, 5, 5, 100, 100, 0.1, 0.2),
        "tarde/demais": (300, 20, 5, 5, 100, 100, 0.1, 0.2),
    })
    ok = elegiveis(por_periodo)
    assert ok.loc["ok/ok"].all()
    assert ok.loc["pouca/release", "dias"] and not ok.loc["pouca/release", "releases"]
    assert ok.loc["pouca/release", "runs"]
    assert ok.loc["poucos/runs", "releases"] and not ok.loc["poucos/runs", "runs"]
    assert not ok.loc["cedo/demais"].any() and not ok.loc["tarde/demais"].any()

    repos = pd.DataFrame({
        "repo": list(ok.index) + ["sem/ia"],
        "primeiro_commit_ia": ["2026-01-15T00:00:00Z"] * 5 + [None],
    })
    etapas = funil(repos, por_periodo, INICIO, FIM).set_index("etapa")
    assert etapas["restantes"].tolist() == [6, 5, 5, 4, 3, 2, 2]
    assert etapas["descartados"].tolist() == [0, 1, 0, 1, 1, 1, 1]

    tabela = comparar(por_periodo).set_index("metrica")
    assert tabela.loc["cfr_ci", "n"] == 2  # ok/ok e pouca/release
    assert tabela.loc["releases_por_semana", "n"] == 2  # ok/ok e poucos/runs


def test_wilcoxon_com_poucos_pares_nao_roda():
    valores = {f"r/{i}": (100, 100, 5, 5, 50, 50, 0.1, 0.1 + 0.01 * (i + 1)) for i in range(MINIMO_PARES - 1)}
    linha = parear(por_periodo_de(valores), "cfr_ci", valores)

    assert linha["n"] == MINIMO_PARES - 1
    assert linha["subiram"] == MINIMO_PARES - 1
    assert math.isnan(linha["p_valor"]) and math.isnan(linha["efeito"])
    assert linha["mediana_depois"] > linha["mediana_antes"]


def test_wilcoxon_com_pares_suficientes_e_todos_empatados():
    subindo = {f"r/{i}": (100, 100, 5, 5, 50, 50, 0.1, 0.1 + 0.01 * (i + 1)) for i in range(MINIMO_PARES)}
    linha = parear(por_periodo_de(subindo), "cfr_ci", subindo)
    assert linha["n"] == MINIMO_PARES
    assert linha["efeito"] == pytest.approx(1.0)  # todos subiram depois
    assert linha["p_valor"] == pytest.approx(2 / 2 ** MINIMO_PARES)  # exato: só a configuração extrema

    iguais = {f"r/{i}": (100, 100, 5, 5, 50, 50, 0.1, 0.1) for i in range(MINIMO_PARES)}
    linha = parear(por_periodo_de(iguais), "cfr_ci", iguais)
    assert linha["empates"] == MINIMO_PARES and math.isnan(linha["p_valor"])


def test_holm_so_nos_testados():
    valores = {f"r/{i}": (100, 100, 5, 5, 50, 50, 0.1, 0.1 + 0.01 * (i + 1)) for i in range(MINIMO_PARES)}
    tabela = comparar(por_periodo_de(valores)).set_index("metrica")
    assert tabela.loc["cfr_ci", "p_ajustado"] == pytest.approx(tabela.loc["cfr_ci", "p_valor"])
    assert tabela.loc["lead_time_release_horas", "n"] == 0
    assert math.isnan(tabela.loc["lead_time_release_horas", "p_ajustado"])


def test_trimestres_contados_a_partir_da_adocao_e_recortados_a_janela():
    linhas = por_trimestre("o/r", T0, releases_feitas_a_mao(), runs_feitos_a_mao(), INICIO, FIM)
    trimestres = [linha["trimestre"] for linha in linhas]
    # 01/10 fica no trimestre -2 (16/10 a 15/01 é o -1); o -2 tem 15 dias e meio na janela e sai
    assert trimestres == [-1, 0, 1, 2]
    menos_um, zero = linhas[0], linhas[1]
    assert menos_um["releases"] == 2 and zero["releases"] == 2
    assert menos_um["dias"] == 91
    # o último trimestre vai de 16/07 a 30/09, recortado na janela
    assert linhas[-1]["dias"] < 91


def test_mann_kendall_e_tendencias():
    assert mann_kendall(pd.Series([1.0, 2.0]))["tendencia"] is None
    crescente = mann_kendall(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], index=[-3, -2, -1, 0, 1, 2]))
    assert crescente["tendencia"] == "increasing" and crescente["tau"] == pytest.approx(1.0)

    # trimestre com poucos repositórios fica fora do teste
    trimestres = pd.DataFrame(
        [{"repo": f"r/{i}", "trimestre": k, "cfr_ci": 0.1 * (k + 3)} for i in range(5) for k in range(-2, 2)]
        + [{"repo": "r/0", "trimestre": -3, "cfr_ci": 0.9}]
    )
    for metrica in ("releases_por_semana", "lead_time_release_horas", "lead_time_commit_horas",
                    "recuperacao_horas"):
        trimestres[metrica] = None
    ok = pd.DataFrame({"dias": True, "releases": True, "runs": True}, index=[f"r/{i}" for i in range(5)])
    medianas, testes = tendencias(trimestres, ok)
    cfr = medianas[medianas["metrica"] == "cfr_ci"].set_index("trimestre")
    assert not cfr.loc[-3, "no_teste"] and cfr.loc[-2, "no_teste"]
    teste = testes.set_index("metrica").loc["cfr_ci"]
    assert teste["pontos"] == 4 and teste["primeiro_trimestre"] == -2
    assert testes.set_index("metrica").loc["recuperacao_horas", "pontos"] == 0

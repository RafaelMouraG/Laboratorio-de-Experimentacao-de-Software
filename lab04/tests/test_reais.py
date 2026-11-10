import math

import pandas as pd
import pytest

from lab04.dashboard.pagina import gerar
from lab04.simulacao import motor, parametros, reais
from lab04.simulacao.gerador import efeito_observado
from lab04.simulacao.testes import mann_whitney, welch


@pytest.fixture(scope="module")
def resultado():
    return reais.rodar()


def test_usa_as_funcoes_da_simulacao_nas_horas_brutas(resultado):
    prs = pd.read_csv(parametros.CSV)
    com = prs.loc[prs["grupo"] == "com_bot", "horas_ate_merge"].to_numpy()
    sem = prs.loc[prs["grupo"] == "sem_bot", "horas_ate_merge"].to_numpy()
    w, m = resultado.testes
    assert w.p == pytest.approx(float(welch(com, sem).p))
    assert m.estatistica == pytest.approx(float(mann_whitney(com, sem).estatistica))
    assert resultado.n == {"com_bot": 30, "sem_bot": 30}


def test_poder_e_a_linha_da_q2_no_efeito_observado(resultado):
    sim = motor.ler()
    efeito = efeito_observado(parametros.calcular())
    for t in resultado.testes:
        linha = sim[
            (sim["situacao"] == "base") & (sim["teste"] == t.teste) & (sim["alfa"] == 0.05)
            & (sim["efeito"] == efeito)
        ].iloc[0]
        assert t.poder[0.05] == linha["rejeicoes"] / linha["n_rep"]


def test_efeito_fora_da_grade_pede_para_rodar_a_q2():
    sim = motor.ler()
    with pytest.raises(ValueError, match="rode a Q2"):
        reais.poder_no_efeito(sim, math.log(4.3), "welch", 0.05)


def test_conclusao_segue_o_p_valor():
    t = reais.Teste("welch", "t", 2.0, 0.03, "g de Hedges", 0.5, {0.05: 0.2, 0.01: 0.05})
    assert reais.conclusao(t) == "H₀ (médias iguais) rejeitada a 5%, não rejeitada a 1%"


def test_secao_6_sai_do_codigo_e_sem_aviso_de_entrega_final(tmp_path, resultado):
    html = gerar(tmp_path / "index.html").read_text(encoding="utf-8")
    secao = html[html.index('<section id="dados-reais">'):]
    secao = secao[: secao.index("</section>")]
    assert "pendente" not in secao
    for t in resultado.testes:
        assert f"{t.p:.4f}".replace(".", ",") in secao
        assert f"{100 * t.poder[0.05]:.1f}%".replace(".", ",") in secao
    assert "associação" in secao

import math

import pandas as pd
import pytest

from lab04.simulacao import motor, parametros, q1, q2
from lab04.simulacao.gerador import efeito_observado


@pytest.fixture(scope="module")
def resultado():
    return q2.rodar()


def test_grade_comeca_em_zero_tem_5_efeitos_e_e_espacada_em_log():
    assert q2.EFEITOS[0] == 0.0
    assert len(q2.EFEITOS) >= 5
    assert list(q2.EFEITOS) == sorted(q2.EFEITOS)
    for m, e in zip(q2.MULTIPLICADORES, q2.EFEITOS):
        assert math.exp(e) == pytest.approx(m)


def test_efeito_zero_e_o_mesmo_ponto_da_q1(resultado):
    zero = resultado[resultado["efeito"] == 0.0].reset_index(drop=True)
    pd.testing.assert_frame_equal(zero, q1.rodar())


def test_efeito_observado_entra_na_grade(resultado):
    assert efeito_observado(parametros.calcular()) in set(resultado["efeito"])


def test_curva_do_mann_whitney_sai_de_5_e_chega_perto_de_100(resultado):
    mw = resultado[(resultado["teste"] == "mann_whitney") & (resultado["alfa"] == 0.05)]
    mw = mw.sort_values("efeito")["proporcao"].to_numpy()
    assert mw[0] == pytest.approx(0.05, abs=0.01)
    assert mw[-1] > 0.99


def _curva(poderes):
    efeitos = [0.0, 1.0, 2.0, 3.0][: len(poderes)]
    return pd.DataFrame({"teste": "welch", "alfa": 0.05, "efeito": efeitos, "proporcao": poderes})


def test_cruzamento_interpola_entre_os_pontos():
    assert q2.cruzamento(_curva([0.05, 0.4, 0.9, 1.0]), "welch") == pytest.approx(1.8)


def test_cruzamento_sem_chegar_no_alvo_da_none():
    assert q2.cruzamento(_curva([0.05, 0.3, 0.6, 0.65]), "welch") is None


def test_cruzamento_no_primeiro_ponto():
    assert q2.cruzamento(_curva([0.85, 0.9]), "welch") == 0.0


def test_csv_versionado_tem_a_q2_atualizada(resultado):
    csv = motor.ler().set_index(motor.CHAVE)
    for _, l in resultado.iterrows():
        assert csv.loc[(l.situacao, l.efeito, l.teste, l.alfa), "rejeicoes"] == l.rejeicoes


def test_tabela_da_q2_no_readme_esta_atualizada(resultado):
    texto = q2.README.read_text(encoding="utf-8")
    bloco = texto.split(q2.INICIO, 1)[1].split(q2.FIM, 1)[0].strip()
    assert bloco == q2.tabela(resultado, efeito_observado(parametros.calcular()))

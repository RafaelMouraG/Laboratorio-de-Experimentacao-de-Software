import json

import numpy as np
import pytest
from scipy import stats

from lab04.dashboard import pagina
from lab04.dashboard.pagina import BOARD, DASHBOARD, REPOSITORIO, gerar, resumo_g2
from lab04.simulacao.testes import mann_whitney, welch


def test_gera_a_pagina_com_os_links_no_topo(tmp_path):
    destino = gerar(tmp_path / "index.html")
    html = destino.read_text(encoding="utf-8")
    assert REPOSITORIO in html and BOARD in html and DASHBOARD in html
    assert html.index(REPOSITORIO) < html.index("</body>")
    # O link do dashboard publicado vem antes de qualquer outro.
    assert html.index(DASHBOARD) < html.index(REPOSITORIO)


def test_pagina_tem_as_sete_secoes_na_ordem_e_os_avisos(tmp_path):
    html = gerar(tmp_path / "index.html").read_text(encoding="utf-8")
    ids = ["pergunta", "g1", "g2", "g3", "g4", "dados-reais", "conclusao"]
    posicoes = [html.index(f'<section id="{id_secao}">') for id_secao in ids]
    assert posicoes == sorted(posicoes)
    assert 'class="selo">S02<' not in html
    assert html.count("entrega final") >= 3


def test_graficos_g1_a_g4_sao_plotly_autocontidos_e_rotulados(tmp_path):
    html = gerar(tmp_path / "index.html").read_text(encoding="utf-8")
    for grafico in ("g1", "g2", "g3", "g4"):
        assert f'id="grafico-{grafico}"' in html
    assert "plotly.js" in html.lower()
    for rotulo in [
        "Tempo até o merge (horas, escala log)",
        "PRs no intervalo (%)",
        "Estatística t",
        "Estatística U",
        "Densidade de probabilidade",
        "t de Welch",
        "Mann-Whitney",
        "faixa de ruído de ±0,4 p.p.",
        "α = 1%",
    ]:
        # O Plotly serializa caracteres não ASCII como escapes dentro do JavaScript.
        assert rotulo in html or json.dumps(rotulo)[1:-1] in html


def test_textos_g3_e_g4_refletem_as_taxas_e_os_poderes_do_csv(tmp_path):
    html = gerar(tmp_path / "index.html").read_text(encoding="utf-8")
    assert "1,56%" in html
    assert "4,38%" in html
    assert "0,07%" in html
    assert "0,84%" in html
    assert "a vantagem não muda de lado" in html
    assert "Cenário base: ×5,0" in html
    assert "Welch não alcança 80%" in html


def test_gerar_le_simulacoes_sem_reexecuta_las(tmp_path, monkeypatch):
    def falhar(*args, **kwargs):
        raise AssertionError("o dashboard não deve recalcular as simulações")

    monkeypatch.setattr(pagina.motor, "simular", falhar)
    gerar(tmp_path / "index.html")


def test_areas_do_g2_usam_os_p_valores_dos_testes():
    com = np.array([2.0, 6.0, 13.0, 25.0, 80.0])
    sem = np.array([1.0, 3.0, 4.0, 7.0, 9.0])
    resumo = resumo_g2(com, sem)
    assert resumo["p_welch"] == pytest.approx(float(welch(com, sem).p))
    assert resumo["p_mann_whitney"] == pytest.approx(float(mann_whitney(com, sem).p))
    assert 2 * stats.norm.sf(resumo["z_u"]) == pytest.approx(resumo["p_mann_whitney"])


def test_gerar_de_novo_sobrescreve_igual(tmp_path):
    destino = tmp_path / "index.html"
    primeira = gerar(destino).read_text(encoding="utf-8")
    assert gerar(destino).read_text(encoding="utf-8") == primeira

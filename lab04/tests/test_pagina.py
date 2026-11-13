import json
import re

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


@pytest.fixture(scope="module")
def html(tmp_path_factory):
    return gerar(tmp_path_factory.mktemp("dashboard") / "index.html").read_text(encoding="utf-8")


def _secao(html, id_secao):
    inicio = html.index(f'<section id="{id_secao}">')
    return html[inicio:html.index("</section>", inicio)]


def _leitura(html, id_secao):
    trecho = _secao(html, id_secao)
    inicio = trecho.index('<p class="leitura">') + len('<p class="leitura">')
    return trecho[inicio:trecho.index("</p>", inicio)]


def test_pagina_tem_as_sete_secoes_na_ordem_e_sem_avisos(html):
    ids = ["pergunta", "g1", "g2", "g3", "g4", "dados-reais", "conclusao", "apendice"]
    posicoes = [html.index(f'<section id="{id_secao}">') for id_secao in ids]
    assert posicoes == sorted(posicoes)
    # Os dados dos gráficos vão em base64 dentro dos <script>, e lá "S02" pode aparecer por acaso.
    texto = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    assert "S02" not in texto
    assert "entrega final" not in texto
    assert "pendente" not in texto


def test_secao_1_tem_hipoteses_origem_e_observacoes(html):
    secao = _secao(html, "pergunta")
    for trecho in ["E[X] = E[Y]", "P(X &gt; Y) = P(Y &gt; X)", "bicaudais", "langflow-ai/langflow",
                   "01/08/2026", "31/10/2026", "490", "371", "60 PRs", "30 com bot e 30 sem", "880.000"]:
        assert trecho in secao


@pytest.mark.parametrize("grafico", ["g1", "g2", "g3", "g4"])
def test_textos_dos_graficos_tem_de_2_a_4_frases(html, grafico):
    texto = _leitura(html, grafico).replace("p.p.", "pp")
    frases = [f for f in re.split(r"[.?!](?=\s|$)", texto) if f.strip()]
    assert 2 <= len(frases) <= 4


def test_textos_g1_e_g2_batem_com_os_dados(html):
    assert "36,8 h" in _leitura(html, "g1") and "3,0 h" in _leitura(html, "g1")
    assert "0,1359" in _leitura(html, "g2") and "0,0022" in _leitura(html, "g2")
    assert "erro tipo II" in _leitura(html, "g2")


def test_secao_7_confronta_palpite_escolhe_teste_e_da_limitacao(html):
    secao = _secao(html, "conclusao")
    for trecho in ["O palpite contra a simulação", "Errou", "Acertou", "Qual teste usar",
                   "<strong>Mann-Whitney.</strong>", "Quando a escolha mudaria", "Principal limitação",
                   "203 PRs", "ver o apêndice", "77,4%", "23,5%", "2,89%", "5,16%"]:
        assert trecho in secao
    assert "A1 —" not in secao


def test_apendice_tem_os_tres_extras_com_numeros_dos_csvs(html):
    secao = _secao(html, "apendice")
    for trecho in ["A1 — Poder × tamanho da amostra", "33 PRs", "203 PRs", "442 PRs", "8 dias", "1,7 mês",
                   "3,6 meses", "mais que o período coletado",
                   "A2 — O melhor teste muda com o tamanho da amostra?", "não troca de lado", "+57,5 p.p.",
                   "A3 — p-valor × tamanho do efeito", "9,0 × 10<sup>−8</sup>", "30.000", "27 min", "33,8 h"]:
        assert trecho in secao


@pytest.mark.parametrize("bloco", ["A2", "A3"])
def test_textos_do_apendice_tem_de_2_a_4_frases(html, bloco):
    secao = _secao(html, "apendice")
    trecho = secao[secao.index(f"<h3>{bloco} —"):]
    inicio = trecho.index('<p class="leitura">') + len('<p class="leitura">')
    texto = re.sub(r"<[^>]+>", "", trecho[inicio:trecho.index("</p>", inicio)]).replace("p.p.", "pp")
    frases = [f for f in re.split(r"[.?!](?=\s|$)", texto) if f.strip()]
    assert 2 <= len(frases) <= 4


def test_graficos_g1_a_g4_sao_plotly_autocontidos_e_rotulados(tmp_path):
    html = gerar(tmp_path / "index.html").read_text(encoding="utf-8")
    for grafico in ("g1", "g2", "g3", "g4", "a1", "a2"):
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


def test_textos_g3_e_g4_refletem_as_taxas_e_os_poderes_do_csv(html):
    assert "1,56%" in html
    assert "4,38%" in html
    assert "0,07%" in html
    assert "0,84%" in html
    assert "a vantagem não muda de lado" in html
    assert "Cenário base: ×5,0" in html
    assert "Welch não alcança 80%" in html
    assert "63,3%" in _leitura(html, "g4")
    assert "Nenhum dos dois fica liberal" in _leitura(html, "g3")


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

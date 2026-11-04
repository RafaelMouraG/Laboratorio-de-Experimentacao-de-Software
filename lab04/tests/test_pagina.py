from lab04.dashboard.pagina import BOARD, REPOSITORIO, gerar


def test_gera_a_pagina_com_os_links_no_topo(tmp_path):
    destino = gerar(tmp_path / "index.html")
    html = destino.read_text(encoding="utf-8")
    assert REPOSITORIO in html and BOARD in html
    assert html.index(REPOSITORIO) < html.index("</body>")


def test_gerar_de_novo_sobrescreve_igual(tmp_path):
    destino = tmp_path / "index.html"
    primeira = gerar(destino).read_text(encoding="utf-8")
    assert gerar(destino).read_text(encoding="utf-8") == primeira

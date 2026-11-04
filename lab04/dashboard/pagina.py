"""Monta a página do dashboard, um HTML que abre sem servidor."""

from __future__ import annotations

from pathlib import Path

REPOSITORIO = "https://github.com/RafaelMouraG/Laboratorio-de-Experimentacao-de-Software"
BOARD = "https://github.com/users/RafaelMouraG/projects/12"
DESTINO = Path(__file__).with_name("index.html")

MODELO = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lab04: Testes de Hipótese</title>
</head>
<body>
<h1>Lab04: t de Welch × Mann-Whitney no tempo até o merge</h1>
<p><a href="{repositorio}">Repositório</a> | <a href="{board}">GitHub Projects</a></p>
</body>
</html>
"""


def gerar(destino: Path = DESTINO) -> Path:
    destino.write_text(MODELO.format(repositorio=REPOSITORIO, board=BOARD), encoding="utf-8")
    return destino

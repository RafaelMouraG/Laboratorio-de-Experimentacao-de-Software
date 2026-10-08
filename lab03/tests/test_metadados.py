import logging

import pytest

from lab03.pipeline.api import ErroAPI
from lab03.pipeline.metadados import coletar_metadados


class APIFalsa:
    def __init__(self, repositorio, contribuidores=1):
        self.repositorio = repositorio
        self.contribuidores = contribuidores
        self.pedidos = []

    def get(self, caminho):
        self.pedidos.append((caminho, None))
        return self.repositorio

    def ultima_pagina(self, caminho, params):
        self.pedidos.append((caminho, params))
        if isinstance(self.contribuidores, BaseException):
            raise self.contribuidores
        return self.contribuidores


def repositorio():
    return {
        "stargazers_count": 1234,
        "language": "Python",
        "default_branch": "main",
        "created_at": "2020-01-01T00:00:00Z",
    }


def test_coleta_metadados_calcula_idade_ate_o_fim_da_janela():
    api = APIFalsa(repositorio(), contribuidores=347)

    metadados = coletar_metadados(api, "o/r", "2025-01-01")

    assert metadados["repo"] == "o/r"
    assert metadados["estrelas"] == 1234
    assert metadados["linguagem"] == "Python"
    assert metadados["default_branch"] == "main"
    assert metadados["criado_em"] == "2020-01-01T00:00:00Z"
    assert metadados["contribuidores"] == 347
    assert metadados["idade_anos"] == pytest.approx(5.002, abs=0.002)


def test_403_de_lista_grande_define_contribuidores_como_none(caplog):
    erro = ErroAPI(
        "/repos/o/r/contributors",
        403,
        "The history or contributor list is too large to list contributors",
    )
    api = APIFalsa(repositorio(), contribuidores=erro)

    with caplog.at_level(logging.WARNING):
        metadados = coletar_metadados(api, "o/r", "2025-01-01")

    assert metadados["contribuidores"] is None
    assert "lista de contribuidores grande demais" in caplog.text

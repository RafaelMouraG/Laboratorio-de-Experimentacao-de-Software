"""Coleta dos metadados usados como fatores da RQ 06."""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone
from typing import Any, Union

from lab03.pipeline.api import ErroAPI, GitHubAPI

log = logging.getLogger(__name__)

DataFim = Union[str, date, datetime]
SEGUNDOS_POR_ANO = 365.25 * 24 * 60 * 60


def _data_fim(valor: DataFim) -> datetime:
    if isinstance(valor, datetime):
        resultado = valor
    elif isinstance(valor, date):
        resultado = datetime.combine(valor, time.max)
    else:
        texto = valor.strip()
        resultado = datetime.fromisoformat(texto.replace("Z", "+00:00"))
        if not isinstance(resultado, datetime):
            raise TypeError(f"fim_janela inválido: {valor!r}")

    if resultado.tzinfo is None:
        return resultado.replace(tzinfo=timezone.utc)
    return resultado.astimezone(timezone.utc)


def _data_criacao(valor: str) -> datetime:
    resultado = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    if resultado.tzinfo is None:
        return resultado.replace(tzinfo=timezone.utc)
    return resultado.astimezone(timezone.utc)


def _idade_anos(criado_em: str, fim_janela: DataFim) -> float:
    criado = _data_criacao(criado_em)
    fim = _data_fim(fim_janela)
    return (fim - criado).total_seconds() / SEGUNDOS_POR_ANO


def _contar_contribuidores(api: GitHubAPI, repo: str) -> int | None:
    caminho = f"/repos/{repo}/contributors"
    params = {"per_page": 1, "anon": "true"}
    try:
        return api.ultima_pagina(caminho, params)
    except ErroAPI as erro:
        mensagem = erro.mensagem.lower()
        if erro.status == 403 and "contributor list is too large" in mensagem:
            log.warning("%s: lista de contribuidores grande demais para a API", repo)
            return None
        raise


def coletar_metadados(api: GitHubAPI, repo: str, fim_janela: DataFim) -> dict[str, Any]:
    """Coleta os fatores da RQ 06 e o branch usado pelas demais coletas."""
    dados = api.get(f"/repos/{repo}")
    criado_em = dados["created_at"]
    return {
        "repo": repo,
        "estrelas": dados["stargazers_count"],
        "linguagem": dados.get("language"),
        "default_branch": dados["default_branch"],
        "criado_em": criado_em,
        "idade_anos": _idade_anos(criado_em, fim_janela),
        "contribuidores": _contar_contribuidores(api, repo),
    }

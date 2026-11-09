"""Rework rate da RQ 08.

Execute da raiz do repositório com ``python -m lab03.analise.rq08``.
"""

from __future__ import annotations

from typing import Iterable

from lab03.metricas.corretiva import eh_corretiva


def _tem_anterior(release: dict) -> bool:
    if "anterior" in release:
        return release["anterior"] is not None
    if "sem_anterior" in release:
        return not release["sem_anterior"]
    raise ValueError("cada release precisa informar `anterior` ou `sem_anterior`")


def rework_rate(releases: Iterable[dict]) -> float | None:
    """Retorna releases corretivas / releases avaliáveis com anterior.

    Cada release deve conter `tag_name`, `body` e a informação de anterioridade
    (`anterior` ou `sem_anterior`). Releases sem anterior não entram no denominador.
    """
    avaliaveis = [release for release in releases if _tem_anterior(release)]
    if not avaliaveis:
        return None

    corretivas = sum(
        eh_corretiva(release, release.get("anterior"))
        for release in avaliaveis
    )
    return corretivas / len(avaliaveis)

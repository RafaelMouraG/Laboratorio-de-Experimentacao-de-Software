"""Faixas de desempenho DORA usadas na RQ 07 e na classificação geral."""

from __future__ import annotations

import math
from statistics import median
from typing import Iterable

RELEASES_POR_SEMANA_MEDIUM = 12 / 52.14


def faixa_frequencia(por_semana: float | None) -> int | None:
    if por_semana is None:
        return None
    if por_semana >= 7:
        return 4
    if por_semana >= 1:
        return 3
    if por_semana >= RELEASES_POR_SEMANA_MEDIUM:
        return 2
    return 1


def faixa_lead_time(horas: float | None) -> int | None:
    if horas is None:
        return None
    if horas < 24:
        return 4
    if horas < 168:
        return 3
    if horas < 720:
        return 2
    return 1


def faixa_cfr(taxa: float | None) -> int | None:
    if taxa is None:
        return None
    if taxa <= 0.15:
        return 4
    if taxa <= 0.30:
        return 3
    if taxa <= 0.45:
        return 2
    return 1


def faixa_recuperacao(horas: float | None) -> int | None:
    if horas is None:
        return None
    if horas < 1:
        return 4
    if horas < 24:
        return 3
    if horas < 168:
        return 2
    return 1


def classificacao_geral(notas: Iterable[int | None]) -> int | None:
    """Retorna a mediana inteira da classificação; menos de 2 notas válidas retorna None.

    A ausência de duas notas válidas impede uma classificação geral confiável e, por
    decisão metodológica, é representada por ``None``.
    """
    validas = [nota for nota in notas if nota is not None]
    if len(validas) < 2:
        return None
    return math.floor(median(validas))

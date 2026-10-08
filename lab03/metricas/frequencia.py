"""Métrica de frequência de releases (RQ 01)."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Iterable, Union

Data = Union[str, date, datetime]


def _data(valor: Data, *, fim: bool = False) -> datetime:
    if isinstance(valor, datetime):
        resultado = valor
    elif isinstance(valor, date):
        resultado = datetime.combine(valor, time.max if fim else time.min)
    else:
        texto = valor.replace("Z", "+00:00")
        resultado = datetime.fromisoformat(texto)
        if fim and len(valor) == 10:
            resultado = resultado.replace(hour=23, minute=59, second=59, microsecond=999999)
    if resultado.tzinfo is None:
        return resultado.replace(tzinfo=timezone.utc)
    return resultado.astimezone(timezone.utc)


def releases_por_semana(
    datas_releases: Iterable[Data],
    inicio: Data,
    fim: Data,
) -> float:
    """Conta releases na janela inclusiva e divide pela duração da janela em semanas."""
    inicio_data = _data(inicio)
    fim_data = _data(fim, fim=True)
    semanas = (fim_data.date() - inicio_data.date()).days / 7
    if semanas <= 0:
        raise ValueError("a janela deve ter duração positiva")

    dentro = sum(
        inicio_data <= _data(data) <= fim_data
        for data in datas_releases
    )
    return dentro / semanas

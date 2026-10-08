"""Lead time for changes (RQ 02), nas duas variantes obrigatórias, em horas.

Cada release chega como `{"published_at": dt, "commits": [dt, ...], "sem_anterior": bool}`.
As datas podem ser `datetime` ou ISO 8601, e um commit também pode ser o dict da coleta (#75),
com a data em `data`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import median
from typing import Iterable, Optional, Union

Data = Union[str, datetime]


def _data(valor: Union[Data, dict]) -> datetime:
    if isinstance(valor, dict):
        valor = valor["data"]
    if isinstance(valor, datetime):
        return valor
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def _horas_dos_commits(release: dict) -> tuple[list[float], int]:
    """(lead time de cada commit, commits descartados por terem data depois da release).

    Release sem anterior não entra no lead time, então não devolve nada.
    """
    if release.get("sem_anterior"):
        return [], 0
    publicada = _data(release["published_at"])
    horas = [(publicada - _data(c)).total_seconds() / 3600 for c in release["commits"]]
    validas = [h for h in horas if h >= 0]
    return validas, len(horas) - len(validas)


def lead_time_release(release: dict) -> Optional[float]:
    """`published_at − commit mais antigo`. None se não tem anterior ou não tem commits novos."""
    horas, _ = _horas_dos_commits(release)
    return max(horas) if horas else None


@dataclass(frozen=True)
class LeadTime:
    mediana_horas: Optional[float]
    valores: int  # releases na variante (a), commits na (b)
    descartados: int  # commits com data depois da release (rebase, relógio errado)


def lead_time_por_release(releases: Iterable[dict]) -> LeadTime:
    """Variante (a): mediana dos lead times de cada release."""
    valores, descartados = [], 0
    for release in releases:
        horas, fora = _horas_dos_commits(release)
        descartados += fora
        if horas:
            valores.append(max(horas))
    return LeadTime(median(valores) if valores else None, len(valores), descartados)


def lead_time_por_commit(releases: Iterable[dict]) -> LeadTime:
    """Variante (b): uma mediana só sobre todos os commits de todas as releases."""
    valores, descartados = [], 0
    for release in releases:
        horas, fora = _horas_dos_commits(release)
        valores.extend(horas)
        descartados += fora
    return LeadTime(median(valores) if valores else None, len(valores), descartados)

"""Coleta dos workflow runs do default branch disparados por push, dentro da janela.

Com filtros, o /actions/runs devolve no máximo 1.000 runs por consulta. Por isso a janela é
consultada mês a mês, e um mês que bate o teto é partido ao meio até cada pedaço caber.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Union

from lab03.metricas.falhas import classificar
from lab03.pipeline.api import GitHubAPI

TETO_BUSCA = 1000
CAMPOS = ("id", "workflow_id", "name", "status", "conclusion", "created_at", "run_started_at", "updated_at", "head_sha")

log = logging.getLogger(__name__)

Dia = Union[str, date]
Intervalo = tuple[datetime, datetime]  # fechado nas duas pontas, precisão de segundo


def _dia(valor: Dia) -> date:
    return valor if isinstance(valor, date) else date.fromisoformat(valor)


def fatias_mensais(inicio: Dia, fim: Dia) -> list[tuple[date, date]]:
    """Meses da janela, com o primeiro e o último cortados nas datas da janela.

    Ex.: 2025-01-15 a 2025-03-10 vira 15..31/jan, 01..28/fev e 01..10/mar.
    """
    atual, fim = _dia(inicio), _dia(fim)
    fatias = []
    while atual <= fim:
        proximo_mes = (atual.replace(day=1) + timedelta(days=32)).replace(day=1)
        fatias.append((atual, min(proximo_mes - timedelta(days=1), fim)))
        atual = proximo_mes
    return fatias


def _como_intervalo(fatia: tuple[date, date]) -> Intervalo:
    return (
        datetime.combine(fatia[0], time.min, timezone.utc),
        datetime.combine(fatia[1], time(23, 59, 59), timezone.utc),
    )


def filtro_created(intervalo: Intervalo) -> str:
    """Dias inteiros viram `AAAA-MM-DD..AAAA-MM-DD`; pedaços menores levam hora."""
    a, b = intervalo
    if a.time() == time.min and b.time() == time(23, 59, 59):
        return f"{a.date()}..{b.date()}"
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return f"{a.strftime(fmt)}..{b.strftime(fmt)}"


def partir(intervalo: Intervalo) -> list[Intervalo]:
    a, b = intervalo
    meio = a + timedelta(seconds=(b - a).total_seconds() // 2)
    return [(a, meio), (meio + timedelta(seconds=1), b)]


def _enxugar(run: dict) -> dict:
    return {campo: run.get(campo) for campo in CAMPOS}


def listar_runs(api: GitHubAPI, repo: str, branch: str, inicio: Dia, fim: Dia) -> list[dict]:
    caminho = f"/repos/{repo}/actions/runs"
    pendentes = [_como_intervalo(f) for f in fatias_mensais(inicio, fim)]
    vistos: dict[int, dict] = {}
    while pendentes:
        intervalo = pendentes.pop(0)
        params = {"branch": branch, "event": "push", "created": filtro_created(intervalo)}
        # mesma chave da 1ª página do paginar, então essa espiada sai do cache depois
        total = api.get(caminho, {"per_page": 100, **params})["total_count"]
        if total >= TETO_BUSCA:
            if intervalo[1] - intervalo[0] >= timedelta(seconds=1):
                log.info("%s: %s tem %d runs, partindo ao meio", repo, params["created"], total)
                pendentes[:0] = partir(intervalo)
                continue
            log.warning("%s: %s tem %d runs num segundo só, ficando com os 1000", repo, params["created"], total)
        for run in api.paginar(caminho, params, chave="workflow_runs"):
            vistos[run["id"]] = _enxugar(run)
    return sorted(vistos.values(), key=lambda r: (r["created_at"], r["id"]))


def contar_validos(runs: list[dict]) -> int:
    """Runs que entram em alguma conta (sucesso ou falha). O funil exige pelo menos 50."""
    return sum(1 for run in runs if classificar(run.get("conclusion")))


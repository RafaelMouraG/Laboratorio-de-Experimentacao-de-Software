"""CFR variante (a), pelo proxy de CI, e tempo de recuperação (RQ 04).

Os runs chegam como saem da coleta (#77): dicts com `workflow_id`, `conclusion`,
`run_started_at`, `updated_at` e `created_at`, com datas em ISO 8601 ou já como `datetime`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from statistics import median
from typing import Iterable, Optional, Union

SUCESSO = "sucesso"
FALHA = "falha"

# Tabela da seção 3 do enunciado. Qualquer outro valor (cancelled, skipped, neutral,
# action_required, stale, vazio/None de run em andamento) é ignorado.
_CONCLUSOES = {
    "success": SUCESSO,
    "failure": FALHA,
    "timed_out": FALHA,
    "startup_failure": FALHA,
}

Data = Union[str, datetime]


def classificar(conclusion: Optional[str]) -> Optional[str]:
    return _CONCLUSOES.get(conclusion or "")


def _data(valor: Data) -> datetime:
    if isinstance(valor, datetime):
        return valor
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def _inicio(run: dict) -> datetime:
    return _data(run.get("run_started_at") or run["created_at"])


def cfr_ci(runs: Iterable[dict]) -> Optional[float]:
    """Falhas / (falhas + sucessos). None se o repo não tem nenhum run válido."""
    contagem = {SUCESSO: 0, FALHA: 0}
    for run in runs:
        tipo = classificar(run.get("conclusion"))
        if tipo:
            contagem[tipo] += 1
    total = contagem[SUCESSO] + contagem[FALHA]
    return contagem[FALHA] / total if total else None


@dataclass(frozen=True)
class Episodio:
    workflow_id: int
    inicio: datetime  # run_started_at da primeira falha
    fim: Optional[datetime]  # updated_at do sucesso que encerrou; None = censurado

    @property
    def censurado(self) -> bool:
        return self.fim is None

    @property
    def horas(self) -> Optional[float]:
        if self.fim is None:
            return None
        return (self.fim - self.inicio).total_seconds() / 3600


def _varrer(runs: Iterable[dict]) -> tuple[list[Episodio], int]:
    """Percorre cada workflow em ordem e devolve (episódios, sequências de falha sem início conhecido).

    Um re-run muda o `run_started_at` do run, então ele entra na ordem no momento em que foi
    re-executado, que é quando a correção de fato aconteceu.
    """
    por_workflow: dict = defaultdict(list)
    for run in runs:
        tipo = classificar(run.get("conclusion"))
        if tipo:
            por_workflow[run["workflow_id"]].append((_inicio(run), run.get("id", 0), tipo, run))

    episodios: list[Episodio] = []
    sem_inicio_conhecido = 0
    for workflow_id, sequencia in por_workflow.items():
        sequencia.sort(key=lambda item: (item[0], item[1]))
        ja_teve_sucesso = False
        aberto: Optional[datetime] = None
        falhando_desde_o_comeco = False
        for comeco, _, tipo, run in sequencia:
            if tipo == FALHA:
                if ja_teve_sucesso:
                    if aberto is None:
                        aberto = comeco
                elif not falhando_desde_o_comeco:
                    # Falha antes de qualquer sucesso na janela: o episódio começou antes da
                    # janela e não sabemos quando. Não entra na mediana, só na contagem.
                    falhando_desde_o_comeco = True
                    sem_inicio_conhecido += 1
            else:
                if aberto is not None:
                    episodios.append(Episodio(workflow_id, aberto, _data(run["updated_at"])))
                    aberto = None
                ja_teve_sucesso = True
        if aberto is not None:
            episodios.append(Episodio(workflow_id, aberto, None))
    return episodios, sem_inicio_conhecido


def episodios(runs: Iterable[dict]) -> list[Episodio]:
    return _varrer(runs)[0]


@dataclass(frozen=True)
class Recuperacao:
    mediana_horas: Optional[float]
    episodios: int
    censurados: int
    sem_inicio_conhecido: int

    @property
    def proporcao_censurados(self) -> Optional[float]:
        return self.censurados / self.episodios if self.episodios else None


def tempo_recuperacao(runs: Iterable[dict]) -> Recuperacao:
    """Mediana, em horas, de todos os episódios fechados de todos os workflows do repo."""
    eps, sem_inicio = _varrer(runs)
    fechados = [e.horas for e in eps if not e.censurado]
    return Recuperacao(
        mediana_horas=median(fechados) if fechados else None,
        episodios=len(eps),
        censurados=len(eps) - len(fechados),
        sem_inicio_conhecido=sem_inicio,
    )

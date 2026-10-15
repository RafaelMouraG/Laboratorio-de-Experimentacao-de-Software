"""Agregação das métricas DORA de um repositório.

``metricas_do_repo`` recebe o resultado completo de ``coleta.avaliar_repo``.
Resultados que ainda estão somente na triagem não têm releases detalhadas nem runs
e, por isso, produzem campos vazios em vez de zeros.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from lab03.metricas.classificacao import (
    classificacao_geral,
    faixa_cfr,
    faixa_frequencia,
    faixa_lead_time,
    faixa_recuperacao,
)
from lab03.metricas.corretiva import cfr_entrega
from lab03.metricas.falhas import cfr_ci, tempo_recuperacao
from lab03.metricas.frequencia import releases_por_semana
from lab03.metricas.lead_time import lead_time_por_commit, lead_time_por_release

Data = str | date | datetime

CAMPOS_METRICAS = (
    "repo",
    "releases_por_semana",
    "faixa_releases",
    "lead_time_release_horas",
    "lead_time_release_avaliadas",
    "lead_time_release_descartados",
    "faixa_lead_time_release",
    "lead_time_commit_horas",
    "lead_time_commit_avaliadas",
    "lead_time_commit_descartados",
    "faixa_lead_time_commit",
    "cfr_ci",
    "cfr_ci_avaliadas",
    "cfr_ci_censuradas",
    "faixa_cfr_ci",
    "cfr_entrega",
    "cfr_entrega_avaliadas",
    "cfr_entrega_falharam",
    "cfr_entrega_censuradas",
    "faixa_cfr_entrega",
    "recuperacao_mediana_horas",
    "recuperacao_episodios",
    "recuperacao_censurados",
    "recuperacao_proporcao_censurados",
    "faixa_recuperacao",
    "classificacao_geral",
)


def metricas_do_repo(resultado: dict[str, Any], inicio: Data, fim: Data) -> dict[str, Any]:
    """Calcula as métricas e as faixas DORA de um repositório aceito.

    ``resultado`` deve conter ``repo``, ``releases`` e ``runs`` quando a coleta
    pesada terminou. Para uma triagem parcial, os campos dependentes dos dados
    detalhados ficam ``None`` ou zero nos contadores, sem transformar ausência em
    observação válida.
    """
    releases = list(resultado.get("releases") or [])
    runs = list(resultado.get("runs") or [])
    completos = "releases" in resultado and "runs" in resultado

    frequencia = releases_por_semana(
        (release["published_at"] for release in releases),
        inicio,
        fim,
    ) if completos else None
    por_release = lead_time_por_release(releases) if completos else None
    por_commit = lead_time_por_commit(releases) if completos else None
    cfr_ci_valor = cfr_ci(runs) if completos else None
    conclusoes_consideradas = sum(
        1 for run in runs if run.get("conclusion") in {"success", "failure", "timed_out", "startup_failure"}
    ) if completos else 0
    recuperacao = tempo_recuperacao(runs) if completos else None
    entrega = cfr_entrega(releases, fim) if completos else None

    notas = [
        faixa_frequencia(frequencia),
        faixa_lead_time(por_release.mediana_horas if por_release else None),
        faixa_cfr(cfr_ci_valor),
    ]
    return {
        "repo": resultado.get("repo", ""),
        "releases_por_semana": frequencia,
        "faixa_releases": faixa_frequencia(frequencia),
        "lead_time_release_horas": por_release.mediana_horas if por_release else None,
        "lead_time_release_avaliadas": por_release.valores if por_release else 0,
        "lead_time_release_descartados": por_release.descartados if por_release else 0,
        "faixa_lead_time_release": faixa_lead_time(por_release.mediana_horas if por_release else None),
        "lead_time_commit_horas": por_commit.mediana_horas if por_commit else None,
        "lead_time_commit_avaliadas": por_commit.valores if por_commit else 0,
        "lead_time_commit_descartados": por_commit.descartados if por_commit else 0,
        "faixa_lead_time_commit": faixa_lead_time(por_commit.mediana_horas if por_commit else None),
        "cfr_ci": cfr_ci_valor,
        "cfr_ci_avaliadas": conclusoes_consideradas,
        "cfr_ci_censuradas": (
            resultado.get("runs_censurados", len(runs) - conclusoes_consideradas)
            if completos else 0
        ),
        "faixa_cfr_ci": faixa_cfr(cfr_ci_valor),
        "cfr_entrega": entrega.taxa if entrega else None,
        "cfr_entrega_avaliadas": entrega.avaliadas if entrega else 0,
        "cfr_entrega_falharam": entrega.falharam if entrega else 0,
        "cfr_entrega_censuradas": entrega.censuradas if entrega else 0,
        "faixa_cfr_entrega": faixa_cfr(entrega.taxa if entrega else None),
        "recuperacao_mediana_horas": recuperacao.mediana_horas if recuperacao else None,
        "recuperacao_episodios": recuperacao.episodios if recuperacao else 0,
        "recuperacao_censurados": recuperacao.censurados if recuperacao else 0,
        "recuperacao_proporcao_censurados": (
            recuperacao.proporcao_censurados if recuperacao else None
        ),
        "faixa_recuperacao": faixa_recuperacao(
            recuperacao.mediana_horas if recuperacao else None
        ),
        "classificacao_geral": classificacao_geral(notas),
    }

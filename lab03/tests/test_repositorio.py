from datetime import datetime, timezone

import pytest

from lab03.metricas.repositorio import metricas_do_repo


def release(publicada, *commits, corretiva=None):
    resultado = {
        "published_at": publicada,
        "commits": list(commits),
        "sem_anterior": False,
    }
    if corretiva is not None:
        resultado["corretiva"] = corretiva
    return resultado


def run(hora, conclusion, workflow=1, atualizado=None):
    inicio = f"2025-03-10T{hora}:00:00Z"
    return {
        "id": hora,
        "workflow_id": workflow,
        "conclusion": conclusion,
        "created_at": inicio,
        "run_started_at": inicio,
        "updated_at": f"2025-03-10T{atualizado or hora}:00:00Z",
    }


def test_agrega_variantes_faixas_e_recuperacao():
    resultado = {
        "repo": "o/exemplo",
        "releases": [
            release("2025-03-15T00:00:00Z", "2025-03-02T00:00:00Z", "2025-03-14T00:00:00Z",
                    corretiva="nao"),
            release("2025-03-20T00:00:00Z", "2025-03-19T00:00:00Z", corretiva="sim"),
        ],
        "runs": [
            run("09:00", "success"),
            run("10:00", "failure"),
            run("11:00", "success", atualizado="11:20"),
        ],
    }

    metricas = metricas_do_repo(resultado, "2025-03-01", "2025-03-31")

    assert metricas["lead_time_release_horas"] == 168
    assert metricas["lead_time_commit_horas"] == 24
    assert metricas["cfr_ci"] == pytest.approx(1 / 3)
    assert metricas["cfr_ci_avaliadas"] == 3
    assert metricas["cfr_entrega"] == pytest.approx(1 / 2)
    assert metricas["cfr_entrega_avaliadas"] == 2
    assert metricas["recuperacao_mediana_horas"] == pytest.approx(1 + 20 / 60)
    assert metricas["recuperacao_episodios"] == 1


def test_triagem_nao_converte_contagens_ausentes_em_zero_valido():
    metricas = metricas_do_repo(
        {"repo": "o/pendente", "metadados": {}, "releases_janela": 5},
        "2025-03-01",
        "2025-03-31",
    )

    assert metricas["repo"] == "o/pendente"
    assert metricas["releases_por_semana"] is None
    assert metricas["cfr_ci"] is None
    assert metricas["recuperacao_mediana_horas"] is None


def test_consenso_incerto_e_censurado_na_cfr_de_entrega():
    resultado = {
        "repo": "o/incerto",
        "releases": [
            release("2025-03-10T00:00:00Z", corretiva="sim"),
            release("2025-03-11T00:00:00Z", corretiva="incerto"),
            release("2025-03-12T00:00:00Z"),
        ],
        "runs": [],
    }

    metricas = metricas_do_repo(resultado, "2025-03-01", "2025-03-31")

    assert metricas["cfr_entrega"] == 1
    assert metricas["cfr_entrega_avaliadas"] == 1
    assert metricas["cfr_entrega_censuradas"] == 2

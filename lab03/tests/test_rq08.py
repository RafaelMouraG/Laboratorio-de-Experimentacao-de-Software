import pandas as pd
import pytest

from lab03.analise.rq08 import (
    juntar_cfr,
    maiores_divergencias,
    rework_rate,
    taxas_por_repositorio,
)


def release(tag, corretiva, sem_anterior=False):
    return {
        "tag_name": tag,
        "published_at": "2026-01-01T00:00:00Z",
        "eh_corretiva": corretiva,
        "sem_anterior": sem_anterior,
    }


def test_rework_rate_com_releases_feitas_a_mao():
    releases = [
        release("v1.0.0", False, sem_anterior=True),
        release("v1.0.1", True),
        release("v1.1.0", False),
        release("v1.1.1", True),
    ]

    assert rework_rate(releases) == pytest.approx(2 / 3)


def test_rework_rate_sem_nenhuma_corretiva():
    releases = [release("v1.0.0", False, sem_anterior=True), release("v1.1.0", False)]

    assert rework_rate(releases) == 0


def test_rework_rate_sem_release_avaliavel():
    assert rework_rate([release("v1.0.0", False, sem_anterior=True)]) is None


def test_rework_rate_aplica_heuristica_quando_flag_nao_foi_precalculada():
    releases = [
        {"tag_name": "v1.0.0", "sem_anterior": True, "commits": [], "body": ""},
        {"tag_name": "v1.0.1", "sem_anterior": False, "commits": [], "body": "Bug fixes"},
        {"tag_name": "v1.1.0", "sem_anterior": False, "commits": [], "body": "New feature"},
    ]

    assert rework_rate(releases) == pytest.approx(0.5)


def test_taxas_por_repositorio_e_divergencias():
    releases = pd.DataFrame([
        {"repo": "o/a", "sem_anterior": True, "eh_corretiva": False},
        {"repo": "o/a", "sem_anterior": False, "eh_corretiva": True},
        {"repo": "o/a", "sem_anterior": False, "eh_corretiva": False},
        {"repo": "o/b", "sem_anterior": False, "eh_corretiva": False},
    ])
    metricas = pd.DataFrame([
        {"repo": "o/a", "cfr_entrega": 0.1, "cfr_entrega_avaliadas": 2,
         "cfr_entrega_censuradas": 0},
        {"repo": "o/b", "cfr_entrega": 0.8, "cfr_entrega_avaliadas": 1,
         "cfr_entrega_censuradas": 0},
    ])

    tabela = juntar_cfr(taxas_por_repositorio(releases), metricas)
    por_repo = tabela.set_index("repo")
    assert por_repo.loc["o/a", "rework_rate"] == pytest.approx(0.5)
    assert por_repo.loc["o/b", "rework_rate"] == 0
    assert maiores_divergencias(tabela, limite=1).iloc[0]["repo"] == "o/b"

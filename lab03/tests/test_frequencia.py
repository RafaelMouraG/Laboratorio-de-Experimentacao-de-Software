from datetime import date

import pytest

from lab03.metricas.frequencia import releases_por_semana


def test_releases_por_semana_considera_apenas_datas_na_janela():
    datas = [date(2025, 1, 1), date(2025, 1, 15), date(2025, 2, 1)]

    assert releases_por_semana(datas, date(2025, 1, 1), date(2025, 1, 29)) == pytest.approx(0.5)


def test_releases_por_semana_inclui_extremos_da_janela():
    datas = ["2025-01-01T00:00:00Z", "2025-01-08T23:59:59Z"]

    assert releases_por_semana(datas, "2025-01-01", "2025-01-08") == pytest.approx(2)


def test_releases_por_semana_rejeita_janela_sem_duracao():
    with pytest.raises(ValueError):
        releases_por_semana([], "2025-01-01", "2025-01-01")

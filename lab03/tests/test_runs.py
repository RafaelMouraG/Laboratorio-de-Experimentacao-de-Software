from datetime import date, datetime, timedelta, timezone

import pytest

from lab03.pipeline.runs import (
    TETO_BUSCA,
    classificar,
    contar_validos,
    fatias_mensais,
    filtro_created,
    listar_runs,
    partir,
)


class APIFalsa:
    """Simula o /actions/runs: filtra pelo `created` e corta em 1000, como a API de verdade."""

    def __init__(self, datas):
        self.runs = [
            {"id": i, "workflow_id": 1, "name": "CI", "status": "completed", "conclusion": "success",
             "created_at": d.strftime("%Y-%m-%dT%H:%M:%SZ"), "run_started_at": None,
             "updated_at": None, "head_sha": "abc", "html_url": "descartado"}
            for i, d in enumerate(datas)
        ]
        self.consultas = []
        self.paginados = []

    def _no_intervalo(self, created):
        a, b = created.split("..")
        if "T" not in a:
            a, b = a + "T00:00:00Z", b + "T23:59:59Z"
        return [r for r in self.runs if a <= r["created_at"] <= b]

    def get(self, caminho, params):
        assert params["event"] == "push" and params["branch"] == "main"
        self.consultas.append(params["created"])
        return {"total_count": len(self._no_intervalo(params["created"]))}

    def paginar(self, caminho, params, chave):
        assert chave == "workflow_runs"
        self.paginados.append(len(self._no_intervalo(params["created"])))
        return self._no_intervalo(params["created"])[:TETO_BUSCA]


def a_cada(inicio, passo, n):
    return [inicio + passo * i for i in range(n)]


def test_fatias_de_janela_que_comeca_no_meio_do_mes():
    assert fatias_mensais("2025-01-15", "2025-03-10") == [
        (date(2025, 1, 15), date(2025, 1, 31)),
        (date(2025, 2, 1), date(2025, 2, 28)),
        (date(2025, 3, 1), date(2025, 3, 10)),
    ]


def test_fatias_de_12_meses_sem_buraco_nem_sobreposicao():
    fatias = fatias_mensais(date(2025, 10, 1), date(2026, 9, 30))
    assert len(fatias) == 12
    assert fatias[0][0] == date(2025, 10, 1) and fatias[-1][1] == date(2026, 9, 30)
    for (_, fim), (comeco, _) in zip(fatias, fatias[1:]):
        assert comeco - fim == timedelta(days=1)


def test_fatias_pegam_fevereiro_bissexto():
    assert fatias_mensais("2028-02-01", "2028-02-29") == [(date(2028, 2, 1), date(2028, 2, 29))]


def test_janela_de_um_dia():
    assert fatias_mensais("2025-05-31", "2025-05-31") == [(date(2025, 5, 31), date(2025, 5, 31))]


def test_filtro_created_usa_dia_ou_hora():
    utc = timezone.utc
    dia_inteiro = (datetime(2025, 1, 1, tzinfo=utc), datetime(2025, 1, 31, 23, 59, 59, tzinfo=utc))
    assert filtro_created(dia_inteiro) == "2025-01-01..2025-01-31"
    pedaco = (datetime(2025, 1, 1, tzinfo=utc), datetime(2025, 1, 16, 11, 59, 59, tzinfo=utc))
    assert filtro_created(pedaco) == "2025-01-01T00:00:00Z..2025-01-16T11:59:59Z"


def test_partir_nao_deixa_buraco():
    utc = timezone.utc
    a, b = datetime(2025, 1, 1, tzinfo=utc), datetime(2025, 1, 31, 23, 59, 59, tzinfo=utc)
    (a1, b1), (a2, b2) = partir((a, b))
    assert a1 == a and b2 == b
    assert a2 - b1 == timedelta(seconds=1)


def test_mes_tranquilo_e_uma_consulta_so():
    api = APIFalsa(a_cada(datetime(2025, 1, 1, tzinfo=timezone.utc), timedelta(hours=6), 100))
    runs = listar_runs(api, "o/r", "main", "2025-01-01", "2025-01-31")
    assert len(runs) == 100
    assert api.consultas == ["2025-01-01..2025-01-31"]


def test_mes_que_bate_o_teto_e_partido_sem_perder_run():
    # 2.500 runs em janeiro: uma consulta só devolveria 1.000
    datas = a_cada(datetime(2025, 1, 1, tzinfo=timezone.utc), timedelta(minutes=17), 2500)
    api = APIFalsa(datas)
    runs = listar_runs(api, "o/r", "main", "2025-01-01", "2025-01-31")
    assert len(runs) == 2500
    assert len({r["id"] for r in runs}) == 2500
    assert len(api.consultas) > 1
    assert max(api.paginados) < TETO_BUSCA  # nenhum pedaço coletado bateu no teto


def test_runs_saem_ordenados_e_so_com_os_campos_combinados():
    utc = timezone.utc
    datas = [datetime(2025, 2, 3, tzinfo=utc), datetime(2025, 1, 20, tzinfo=utc)]
    runs = listar_runs(APIFalsa(datas), "o/r", "main", "2025-01-01", "2025-02-28")
    assert [r["created_at"][:10] for r in runs] == ["2025-01-20", "2025-02-03"]
    assert "html_url" not in runs[0]
    assert set(runs[0]) == {"id", "workflow_id", "name", "status", "conclusion", "created_at",
                            "run_started_at", "updated_at", "head_sha"}


def test_runs_fora_da_janela_ficam_de_fora():
    utc = timezone.utc
    datas = [datetime(2024, 12, 31, 23, 59, tzinfo=utc), datetime(2025, 1, 1, tzinfo=utc),
             datetime(2025, 3, 31, 23, 59, 59, tzinfo=utc), datetime(2025, 4, 1, tzinfo=utc)]
    runs = listar_runs(APIFalsa(datas), "o/r", "main", "2025-01-01", "2025-03-31")
    assert len(runs) == 2


def test_classificar_e_o_mesmo_das_metricas():
    from lab03.metricas.falhas import classificar as original
    assert classificar is original


@pytest.mark.parametrize("conclusion, conta", [
    ("success", 1), ("failure", 1), ("timed_out", 1), ("startup_failure", 1),
    ("cancelled", 0), ("skipped", 0), ("neutral", 0), ("action_required", 0), ("stale", 0), (None, 0),
])
def test_contar_validos_segue_a_tabela(conclusion, conta):
    assert contar_validos([{"conclusion": conclusion}]) == conta

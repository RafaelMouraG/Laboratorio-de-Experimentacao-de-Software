from datetime import datetime, timezone

import pytest

from lab03.metricas.falhas import FALHA, SUCESSO, cfr_ci, classificar, episodios, tempo_recuperacao

_ids = iter(range(1, 10_000))


def run(hora, conclusion, workflow=1, termina=None, dia=10):
    """Run do workflow `workflow` começando às `hora` (HH:MM) do dia `dia` de março de 2025."""
    inicio = f"2025-03-{dia:02d}T{hora}:00Z"
    return {
        "id": next(_ids),
        "workflow_id": workflow,
        "conclusion": conclusion,
        "created_at": inicio,
        "run_started_at": inicio,
        "updated_at": f"2025-03-{dia:02d}T{termina or hora}:00Z",
    }


@pytest.fixture
def exemplo_do_enunciado():
    # workflow CI, branch main, tabela da RQ 04
    return [
        run("09:00", "success"),
        run("10:00", "failure"),
        run("10:30", "failure"),
        run("11:15", "success", termina="11:20"),
    ]


@pytest.mark.parametrize(
    "conclusion, esperado",
    [
        ("success", SUCESSO),
        ("failure", FALHA),
        ("timed_out", FALHA),
        ("startup_failure", FALHA),
        ("cancelled", None),
        ("skipped", None),
        ("neutral", None),
        ("action_required", None),
        ("stale", None),
        ("", None),
        (None, None),
    ],
)
def test_classificar_segue_a_tabela_da_secao_3(conclusion, esperado):
    assert classificar(conclusion) == esperado


def test_cfr_ci_ignora_cancelados(exemplo_do_enunciado):
    runs = exemplo_do_enunciado + [run("12:00", "cancelled"), run("12:05", "skipped")]
    assert cfr_ci(runs) == pytest.approx(2 / 4)


def test_cfr_ci_sem_runs_validos():
    assert cfr_ci([run("08:00", "cancelled"), run("09:00", None)]) is None
    assert cfr_ci([]) is None


def test_exemplo_do_enunciado_da_1h20(exemplo_do_enunciado):
    (ep,) = episodios(exemplo_do_enunciado)
    assert ep.inicio == datetime(2025, 3, 10, 10, 0, tzinfo=timezone.utc)
    assert ep.horas == pytest.approx(80 / 60)
    assert tempo_recuperacao(exemplo_do_enunciado).mediana_horas == pytest.approx(80 / 60)


def test_ordem_de_chegada_nao_importa(exemplo_do_enunciado):
    embaralhado = list(reversed(exemplo_do_enunciado))
    assert tempo_recuperacao(embaralhado).mediana_horas == pytest.approx(80 / 60)


def test_cancelado_no_meio_nao_fecha_nem_abre(exemplo_do_enunciado):
    runs = exemplo_do_enunciado[:2] + [run("10:10", "cancelled")] + exemplo_do_enunciado[2:]
    (ep,) = episodios(runs)
    assert ep.horas == pytest.approx(80 / 60)


def test_falha_nunca_recuperada_fica_censurada():
    runs = [run("09:00", "success"), run("10:00", "failure"), run("11:00", "timed_out")]
    (ep,) = episodios(runs)
    assert ep.censurado and ep.horas is None
    r = tempo_recuperacao(runs)
    assert r.mediana_horas is None
    assert (r.episodios, r.censurados, r.proporcao_censurados) == (1, 1, 1.0)


def test_mediana_usa_so_os_fechados_e_conta_os_censurados():
    runs = [
        run("08:00", "success"),
        run("09:00", "failure"),
        run("10:00", "success", termina="10:00"),  # 1 h
        run("11:00", "failure"),
        run("14:00", "success", termina="14:00"),  # 3 h
        run("15:00", "startup_failure"),  # nunca recupera
    ]
    r = tempo_recuperacao(runs)
    assert r.mediana_horas == pytest.approx(2.0)
    assert r.censurados == 1
    assert r.proporcao_censurados == pytest.approx(1 / 3)


def test_workflows_intercalados_nao_se_misturam():
    runs = [
        run("09:00", "success", workflow="ci"),
        run("09:00", "success", workflow="lint"),
        run("10:00", "failure", workflow="ci"),
        run("10:30", "success", workflow="lint", termina="10:31"),  # não fecha o episódio do ci
        run("11:00", "failure", workflow="lint"),
        run("13:00", "success", workflow="ci", termina="13:00"),  # ci: 3 h
        run("11:30", "success", workflow="lint", termina="11:30"),  # lint: 0,5 h
    ]
    duracoes = sorted(e.horas for e in episodios(runs))
    assert duracoes == pytest.approx([0.5, 3.0])
    assert tempo_recuperacao(runs).mediana_horas == pytest.approx(1.75)


def test_falha_antes_do_primeiro_sucesso_nao_abre_episodio():
    runs = [
        run("08:00", "failure"),
        run("08:30", "failure"),
        run("09:00", "success"),
        run("10:00", "failure"),
        run("10:30", "success", termina="10:30"),
    ]
    r = tempo_recuperacao(runs)
    assert r.episodios == 1
    assert r.mediana_horas == pytest.approx(0.5)
    assert r.sem_inicio_conhecido == 1  # uma sequência, não duas falhas


def test_episodio_que_atravessa_dias():
    runs = [
        run("22:00", "success", dia=10),
        run("23:00", "failure", dia=10),
        run("07:00", "success", dia=12, termina="07:30"),
    ]
    assert tempo_recuperacao(runs).mediana_horas == pytest.approx(32.5)


def test_repo_so_com_runs_ignorados():
    r = tempo_recuperacao([run("09:00", "skipped"), run("10:00", "cancelled")])
    assert r.mediana_horas is None
    assert r.episodios == 0
    assert r.proporcao_censurados is None


def test_aceita_datetime_e_cai_para_created_at():
    inicio = datetime(2025, 3, 10, 9, 0, tzinfo=timezone.utc)
    runs = [
        {"id": 1, "workflow_id": 7, "conclusion": "success", "created_at": inicio,
         "run_started_at": None, "updated_at": inicio},
        {"id": 2, "workflow_id": 7, "conclusion": "failure", "created_at": "2025-03-10T10:00:00Z",
         "run_started_at": None, "updated_at": "2025-03-10T10:05:00Z"},
        {"id": 3, "workflow_id": 7, "conclusion": "success", "created_at": "2025-03-10T12:00:00Z",
         "run_started_at": "2025-03-10T12:00:00Z", "updated_at": "2025-03-10T12:00:00Z"},
    ]
    assert tempo_recuperacao(runs).mediana_horas == pytest.approx(2.0)

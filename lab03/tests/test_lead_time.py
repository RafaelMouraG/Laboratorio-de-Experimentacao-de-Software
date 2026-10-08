from datetime import datetime, timedelta, timezone

import pytest

from lab03.metricas.lead_time import (
    LeadTime,
    lead_time_por_commit,
    lead_time_por_release,
    lead_time_release,
)


def dia(d, mes=3, hora=0):
    return datetime(2025, mes, d, hora, tzinfo=timezone.utc)


def release(publicada, *commits, sem_anterior=False):
    return {"published_at": publicada, "commits": list(commits), "sem_anterior": sem_anterior}


@pytest.fixture
def v1_1():
    # exemplo da RQ 02: v1.1 publicada em 15/03 com commits de 02/03, 10/03 e 14/03
    return release(dia(15), dia(2), dia(10), dia(14))


def test_exemplo_do_enunciado_variante_a(v1_1):
    assert lead_time_release(v1_1) == 312
    assert lead_time_por_release([v1_1]) == LeadTime(312, 1, 0)


def test_exemplo_do_enunciado_variante_b(v1_1):
    # a release contribui com 312, 120 e 24 h; a mediana dessas três é 120
    assert lead_time_por_commit([v1_1]) == LeadTime(120, 3, 0)


def test_contribuicao_da_release_se_soma_as_outras_na_variante_b(v1_1):
    outra = release(dia(20), dia(19), dia(19, hora=12))  # 24 h e 12 h
    # valores: 312, 120, 24, 24, 12 -> mediana 24
    assert lead_time_por_commit([v1_1, outra]) == LeadTime(24, 5, 0)


def test_commit_esquecido_explode_a_e_quase_nao_mexe_na_b():
    recentes = [dia(14, hora=h) for h in range(10)]  # 10 commits entre 15 h e 24 h antes
    sem_esquecido = release(dia(15), *recentes)
    com_esquecido = release(dia(15), dia(1, mes=1), *recentes)

    a_antes, a_depois = lead_time_release(sem_esquecido), lead_time_release(com_esquecido)
    b_antes = lead_time_por_commit([sem_esquecido]).mediana_horas
    b_depois = lead_time_por_commit([com_esquecido]).mediana_horas

    assert a_antes == 24 and a_depois == 73 * 24  # 01/01 a 15/03
    assert b_antes == 19.5 and b_depois == 20  # a mediana anda só meio commit


def test_release_sem_commits_novos_fica_de_fora():
    vazia = release(dia(15))
    assert lead_time_release(vazia) is None
    assert lead_time_por_release([vazia, release(dia(15), dia(14))]) == LeadTime(24, 1, 0)


def test_repo_com_uma_unica_release_da_tudo_none():
    unica = release(dia(15), dia(2), dia(10), sem_anterior=True)
    assert lead_time_release(unica) is None
    assert lead_time_por_release([unica]) == LeadTime(None, 0, 0)
    assert lead_time_por_commit([unica]) == LeadTime(None, 0, 0)


def test_repo_sem_releases():
    assert lead_time_por_release([]) == LeadTime(None, 0, 0)
    assert lead_time_por_commit([]) == LeadTime(None, 0, 0)


def test_commit_com_data_futura_e_descartado_e_contado(v1_1):
    v1_1["commits"].append(dia(16))  # depois da publicação
    assert lead_time_release(v1_1) == 312
    assert lead_time_por_release([v1_1]) == LeadTime(312, 1, 1)
    assert lead_time_por_commit([v1_1]) == LeadTime(120, 3, 1)


def test_release_so_com_commits_futuros_vira_none_mas_conta_os_descartes():
    futura = release(dia(15), dia(16), dia(17))
    assert lead_time_release(futura) is None
    assert lead_time_por_release([futura]) == LeadTime(None, 0, 2)


def test_commit_na_hora_exata_da_release_vale_zero():
    assert lead_time_release(release(dia(15), dia(15))) == 0


def test_aceita_iso_e_o_formato_da_coleta():
    coletada = {
        "published_at": "2025-03-15T00:00:00Z",
        "commits": [{"sha": "a", "data": "2025-03-02T00:00:00Z", "mensagem": "feat"}, "2025-03-14T00:00:00Z"],
        "sem_anterior": False,
    }
    assert lead_time_release(coletada) == 312
    assert lead_time_por_commit([coletada]).mediana_horas == (312 + 24) / 2


def test_fuso_horario_diferente_e_respeitado():
    publicada = datetime(2025, 3, 15, 12, tzinfo=timezone.utc)
    commit = datetime(2025, 3, 15, 6, tzinfo=timezone(timedelta(hours=-3)))  # 09:00 UTC
    assert lead_time_release(release(publicada, commit)) == 3

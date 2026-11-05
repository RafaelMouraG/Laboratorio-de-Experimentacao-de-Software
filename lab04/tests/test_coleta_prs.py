from lab04.data.coleta_prs import elegivel, entra_no_grupo, horas_ate_merge

CRIADO, MERGEADO = "2026-08-25T10:00:00Z", "2026-08-25T13:30:00Z"


def pr(login="ana", tipo="User", titulo="fix: algo", mergeado_em=MERGEADO):
    return {"user": {"login": login, "type": tipo}, "title": titulo, "created_at": CRIADO,
            "pull_request": {"merged_at": mergeado_em}}


def review(login, tipo, quando):
    return {"user": {"login": login, "type": tipo}, "submitted_at": quando}


CODERABBIT = "coderabbitai[bot]"


def test_horas_ate_merge():
    assert horas_ate_merge(CRIADO, MERGEADO) == 3.5


def test_elegivel_tira_bot_sincronizacao_e_merge_rapido():
    assert elegivel(pr())
    assert not elegivel(pr(login="dependabot[bot]", tipo="Bot"))
    assert not elegivel(pr(titulo="Merge release-1.12.6 into main"))
    assert not elegivel(pr(mergeado_em="2026-08-25T10:09:00Z"))
    assert elegivel(pr(mergeado_em="2026-08-25T10:10:00Z"))


def test_com_bot_exige_review_antes_do_merge():
    antes = review(CODERABBIT, "Bot", "2026-08-25T11:00:00Z")
    depois = review(CODERABBIT, "Bot", "2026-08-25T14:00:00Z")
    assert entra_no_grupo("com_bot", [antes], MERGEADO)
    assert not entra_no_grupo("com_bot", [depois], MERGEADO)
    assert not entra_no_grupo("com_bot", [review("ana", "User", "2026-08-25T11:00:00Z")], MERGEADO)


def test_sem_bot_nao_aceita_review_de_nenhum_bot():
    assert entra_no_grupo("sem_bot", [review("ana", "User", "2026-08-25T11:00:00Z")], MERGEADO)
    assert not entra_no_grupo("sem_bot", [review("copilot[bot]", "Bot", "2026-08-25T11:00:00Z")], MERGEADO)

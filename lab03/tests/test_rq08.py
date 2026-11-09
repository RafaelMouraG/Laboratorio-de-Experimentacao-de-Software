import pytest

from lab03.analise.rq08 import rework_rate


def release(tag, anterior, notas=""):
    return {
        "tag_name": tag,
        "anterior": anterior,
        "body": notas,
    }


def test_rework_rate_ignora_release_sem_anterior_e_conta_corretivas():
    releases = [
        release("v1.0.0", None, "Bug fixes"),
        release("v1.0.1", {"tag_name": "v1.0.0"}, "Bug fixes"),
        release("v1.1.0", {"tag_name": "v1.0.1"}, "New feature"),
        release("v1.1.1", {"tag_name": "v1.1.0"}, "Bug fix"),
    ]

    assert rework_rate(releases) == pytest.approx(2 / 3)


def test_rework_rate_sem_release_corretiva_retorna_zero():
    releases = [
        release("v1.0.1", {"tag_name": "v1.0.0"}, "New feature"),
        release("v1.1.0", {"tag_name": "v1.0.1"}, "New feature"),
    ]

    assert rework_rate(releases) == 0


def test_rework_rate_sem_release_avaliavel_retorna_none():
    assert rework_rate([release("v1.0.0", None, "Bug fix")]) is None


def test_rework_rate_exige_informacao_de_anterioridade():
    with pytest.raises(ValueError, match="anterior"):
        rework_rate([{"tag_name": "v1.0.1", "body": "Bug fix"}])

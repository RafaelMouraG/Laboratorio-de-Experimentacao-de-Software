import csv

import pytest

from lab03.validacao.concordancia import (
    ErroRotulagem,
    concordancia_dimensao,
    consenso,
    executar,
    faixa_landis_koch,
)


def _escrever(caminho, campos, linhas):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(linhas)


def _planilhas(tmp_path, repos, releases):
    campos_repos = ("repo", "url", "tipo_projeto", "entregas_reais", "observacao")
    campos_releases = ("repo", "tag_name", "url_release", "url_compare", "corretiva", "observacao")
    pasta = tmp_path / "rotulos"
    for avaliador, rotulos_repos, rotulos_releases in zip(
        ("mateusdsoc", "RafaelMouraG", "Athoosz"), repos, releases
    ):
        _escrever(pasta / f"{avaliador}_repos.csv", campos_repos, rotulos_repos)
        _escrever(pasta / f"{avaliador}_releases.csv", campos_releases, rotulos_releases)
    return tmp_path


def _repo(repo, projeto, entrega):
    return {"repo": repo, "url": f"https://github.com/{repo}", "tipo_projeto": projeto,
            "entregas_reais": entrega, "observacao": ""}


def _release(corretiva):
    return {"repo": "o/r", "tag_name": "v1", "url_release": "release",
            "url_compare": "compare", "corretiva": corretiva, "observacao": ""}


def test_concordancia_perfeita_tem_kappa_um():
    assert concordancia_dimensao([["sim", "sim", "sim"], ["nao", "nao", "nao"]]) == (1.0, 100.0)


def test_exemplo_da_wikipedia():
    contagens = [
        [0, 0, 0, 0, 14],
        [0, 2, 6, 4, 2],
        [0, 0, 3, 5, 6],
        [0, 3, 9, 2, 0],
        [2, 2, 8, 1, 1],
        [7, 7, 0, 0, 0],
        [3, 2, 6, 3, 0],
        [2, 5, 3, 2, 2],
        [6, 5, 2, 1, 0],
        [0, 2, 2, 3, 7],
    ]
    dados = [[categoria for categoria, quantidade in enumerate(linha) for _ in range(quantidade)]
             for linha in contagens]
    assert concordancia_dimensao(dados)[0] == pytest.approx(0.210, abs=0.002)


def test_maioria_e_empate():
    assert consenso(["sim", "nao", "sim"]) == "sim"
    assert consenso(["sim", "nao", "incerto"]) is None


def test_faixas_landis_koch():
    assert faixa_landis_koch(-0.1) == "pobre"
    assert faixa_landis_koch(0.21) == "razoavel"
    assert faixa_landis_koch(0.81) == "quase perfeita"


def test_valor_invalido_gera_erro(tmp_path):
    repos = [[_repo("o/r", "invalido", "sim")]] * 3
    releases = [[_release("sim")]] * 3
    with pytest.raises(ErroRotulagem, match="valor inválido"):
        executar(_planilhas(tmp_path, repos, releases))


def test_maioria_e_empate_sao_escritos(tmp_path):
    repos = [
        [_repo("o/r", "aplicacao", "sim"), _repo("o/s", "cli", "sim")],
        [_repo("o/r", "aplicacao", "sim"), _repo("o/s", "biblioteca", "sim")],
        [_repo("o/r", "aplicacao", "sim"), _repo("o/s", "outro", "sim")],
    ]
    releases = [[_release("sim")], [_release("sim")], [_release("nao")]]
    executar(_planilhas(tmp_path, repos, releases))
    assert "consenso_tipo_projeto" in (tmp_path / "consenso_repos.csv").read_text()
    empates = list(csv.DictReader((tmp_path / "empates.csv").open(encoding="utf-8")))
    assert len(empates) == 1
    assert empates[0]["item"] == "o/s"

import csv

import pandas as pd
import pytest

from lab03.validacao.concordancia import ErroRotulagem
from lab03.validacao.precisao_ia import SEM_CONSENSO, consenso, ler_planilha, precisao
from lab03.validacao.sortear_ia import CAMPOS_ROTULO, gravar, sortear, um_por_commit


def rastros():
    return pd.DataFrame([
        {"sha": "a", "repo": "o/r", "data": "2026-01-02T00:00:00Z", "ferramenta": "Claude", "familia": "autoria"},
        {"sha": "a", "repo": "o/r", "data": "2026-01-02T00:00:00Z", "ferramenta": "Claude", "familia": "branch"},
        {"sha": "b", "repo": "o/r", "data": "2026-01-01T00:00:00Z", "ferramenta": "Copilot", "familia": "autoria"},
        {"sha": "c", "repo": "o/s", "data": "2026-03-01T00:00:00Z", "ferramenta": "Codex", "familia": "label"},
    ])


def test_commit_com_dois_rastros_vira_uma_linha():
    commits = um_por_commit(rastros())
    assert len(commits) == 3
    a = commits.set_index("sha").loc["a"]
    assert a["ferramentas"] == "Claude" and a["familias"] == "autoria;branch"


def test_sorteio_e_sempre_o_mesmo_e_tem_o_link():
    commits = um_por_commit(rastros())
    primeiro, segundo = sortear(commits, n=2), sortear(commits, n=2)
    assert primeiro.equals(segundo)
    assert all(u == f"https://github.com/{r}/commit/{s}" for r, s, u in zip(primeiro.repo, primeiro.sha, primeiro.url))


def test_planilha_nao_mostra_a_deteccao_e_nao_e_sobrescrita(tmp_path):
    amostra = sortear(um_por_commit(rastros()), n=3)
    assert gravar(tmp_path, amostra, avaliadores=("ana",)) == []
    planilha = tmp_path / "rotulos" / "ana_ia.csv"
    with planilha.open(encoding="utf-8") as arquivo:
        cabecalho = next(csv.reader(arquivo))
    assert tuple(cabecalho) == CAMPOS_ROTULO and "ferramentas" not in cabecalho
    planilha.write_text("preenchida", encoding="utf-8")
    assert gravar(tmp_path, amostra, avaliadores=("ana",)) == [planilha]
    assert planilha.read_text(encoding="utf-8") == "preenchida"


def test_consenso_pela_maioria():
    assert consenso(["sim", "sim", "nao"]) == "sim"
    assert consenso(["nao", "incerto", "nao"]) == "nao"
    assert consenso(["sim", "nao", "incerto"]) == SEM_CONSENSO


def test_precisao_deixa_incerto_e_sem_consenso_de_fora():
    por_avaliador = {
        "ana": {"a": "sim", "b": "sim", "c": "incerto", "d": "sim"},
        "bia": {"a": "sim", "b": "nao", "c": "incerto", "d": "nao"},
        "caio": {"a": "nao", "b": "nao", "c": "sim", "d": "incerto"},
    }
    resultado = precisao(por_avaliador)
    assert resultado["decisoes"] == {"a": "sim", "b": "nao", "c": "incerto", "d": SEM_CONSENSO}
    assert (resultado["sim"], resultado["nao"], resultado["incerto"], resultado["sem_consenso"]) == (1, 1, 1, 1)
    assert resultado["precisao"] == 0.5


def test_planilhas_com_commits_diferentes_sao_recusadas():
    with pytest.raises(ErroRotulagem):
        precisao({"ana": {"a": "sim"}, "bia": {"b": "sim"}})


def test_rotulo_vazio_ou_com_outra_grafia_e_recusado(tmp_path):
    caminho = tmp_path / "ana_ia.csv"
    caminho.write_text("repo,sha,url,com_agente,observacao\no/r,abc1234,u,Sim,\n", encoding="utf-8")
    with pytest.raises(ErroRotulagem):
        ler_planilha(caminho)
    caminho.write_text("repo,sha,url,com_agente,observacao\no/r,abc1234,u,sim,\n", encoding="utf-8")
    assert ler_planilha(caminho) == {"abc1234": "sim"}

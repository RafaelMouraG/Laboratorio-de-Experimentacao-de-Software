import csv
import json
from datetime import date

import pytest
import requests

from lab03.pipeline import __main__ as cli
from lab03.pipeline.api import GitHubAPI
from lab03.pipeline.coleta import (
    MARCADOR,
    MOTIVO_LIMITE,
    MOTIVO_POUCAS_RELEASES,
    MOTIVO_POUCOS_RUNS,
    executar,
    montar_funil,
    pasta_repo,
)
from lab03.pipeline.selecao import MOTIVO_SEM_ACTIONS

INICIO, FIM = date(2025, 1, 1), date(2025, 1, 31)


def resposta(corpo, status=200):
    r = requests.Response()
    r.status_code = status
    r._content = json.dumps(corpo).encode()
    r.headers.update({"X-RateLimit-Remaining": "4000", "X-RateLimit-Reset": "0"})
    return r


def release(tag, dia):
    return {"tag_name": tag, "published_at": dia + "T12:00:00Z", "draft": False, "prerelease": False,
            "html_url": f"https://x/{tag}"}


def run(i, conclusion="success"):
    return {"id": i, "workflow_id": 1, "name": "ci", "status": "completed", "conclusion": conclusion,
            "created_at": "2025-01-10T00:00:00Z", "run_started_at": "2025-01-10T00:00:00Z",
            "updated_at": "2025-01-10T00:05:00Z", "head_sha": f"s{i}"}


class Repo:
    def __init__(self, nome, estrelas, actions=True, releases=6, runs=60):
        self.nome, self.estrelas, self.actions = nome, estrelas, actions
        # v0 fica fora da janela e serve de anterior para a v1
        self.releases = [release("v0", "2024-12-01")] + [
            release(f"v{i}", f"2025-01-{i + 1:02d}") for i in range(1, releases + 1)
        ]
        self.runs = [run(i, "failure" if i % 10 == 0 else "success") for i in range(runs)] + [
            run(1000, "cancelled")
        ]


class SessaoFalsa:
    """Responde pelo caminho, como o GitHub, e conta as chamadas. `parar_em` simula um Ctrl+C."""

    def __init__(self, repos, parar_em=None):
        self.repos = {r.nome: r for r in repos}
        self.headers = {}
        self.pedidos = []
        self.parar_em = parar_em

    def get(self, url, params=None, timeout=None):
        if self.parar_em is not None and len(self.pedidos) == self.parar_em:
            raise KeyboardInterrupt
        self.pedidos.append((url, params))
        caminho = url.removeprefix("https://api.github.com")
        if caminho == "/search/repositories":
            if "1000..2000" not in params["q"]:
                return resposta({"total_count": 0, "items": []})
            itens = [{"full_name": r.nome, "stargazers_count": r.estrelas} for r in self.repos.values()]
            return resposta({"total_count": len(itens), "items": itens})
        partes = caminho.split("/")
        repo = self.repos["/".join(partes[2:4])]
        resto = "/".join(partes[4:])
        if resto == "":
            return resposta({"stargazers_count": repo.estrelas, "language": "Python",
                             "default_branch": "main", "created_at": "2020-01-01T00:00:00Z"})
        if resto == "actions/workflows":
            return resposta({"total_count": int(repo.actions)})
        if resto == "contributors":
            return resposta([{"login": "a"}])
        if resto == "releases":
            return resposta(repo.releases)
        if resto.startswith("compare/"):
            commit = {"sha": "c", "commit": {"author": {"date": "2025-01-01T00:00:00Z"}, "message": "m"}}
            return resposta({"total_commits": 1, "commits": [commit]})
        if resto == "actions/runs":
            return resposta({"total_count": len(repo.runs), "workflow_runs": repo.runs})
        raise AssertionError(caminho)


REPOS = [
    Repo("o/bom", 1900),
    Repo("o/sem-actions", 1800, actions=False),
    Repo("o/poucas-releases", 1700, releases=3),
    Repo("o/poucos-runs", 1600, runs=40),
    Repo("o/outro-bom", 1500),
    Repo("o/nem-visto", 1400),
]


def rodar(tmp_path, sessao, limite=2):
    api = GitHubAPI("t", tmp_path / "cache", sessao=sessao, dormir=lambda s: None)
    return executar(api, ["1000..2000", ">10000"], INICIO, FIM, limite, tmp_path / "cache", tmp_path / "data")


def ler(caminho):
    with open(caminho, encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def test_para_no_limite_e_gera_os_csvs(tmp_path):
    funil = rodar(tmp_path, SessaoFalsa(REPOS))

    repos = ler(tmp_path / "data/repos.csv")
    assert [r["repo"] for r in repos] == ["o/bom", "o/outro-bom"]
    assert repos[0]["releases"] == "6"
    assert repos[0]["runs_validos"] == "60"
    assert repos[0]["runs_falha"] == "6"
    assert repos[0]["default_branch"] == "main"

    releases = ler(tmp_path / "data/releases.csv")
    assert len(releases) == 12
    assert releases[0]["commits"] == "1"
    assert releases[0]["sem_anterior"] == "False"

    runs = ler(tmp_path / "data/runs.csv")
    assert len(runs) == 120  # o cancelled fica de fora
    assert {r["classe"] for r in runs} == {"sucesso", "falha"}

    assert ler(tmp_path / "data/funil.csv") == [
        {k: str(v) for k, v in linha.items()} for linha in funil.linhas
    ]
    assert not (pasta_repo(tmp_path / "cache", "o/nem-visto") / MARCADOR).exists()


def test_funil_conta_cada_motivo_na_sua_etapa(tmp_path):
    funil = rodar(tmp_path, SessaoFalsa(REPOS))

    resumo = [(l["etapa"], l["restantes"], l["descartados"], l["motivo"]) for l in funil.linhas]
    assert resumo == [
        ("candidatos da busca", 6, 0, ""),
        ("com GitHub Actions", 4, 1, MOTIVO_SEM_ACTIONS),
        ("metadados coletados", 4, 0, ""),
        (">= 5 releases na janela", 3, 1, MOTIVO_POUCAS_RELEASES),
        (">= 50 runs válidos na janela", 2, 1, MOTIVO_POUCOS_RUNS),
        ("amostra final (limite 2)", 2, 1, MOTIVO_LIMITE),
    ]


def test_segunda_execucao_nao_chama_a_api(tmp_path):
    rodar(tmp_path, SessaoFalsa(REPOS))
    sessao = SessaoFalsa(REPOS)

    rodar(tmp_path, sessao)

    assert sessao.pedidos == []
    assert len(ler(tmp_path / "data/repos.csv")) == 2


def test_ctrl_c_no_meio_continua_sem_repetir_chamadas(tmp_path):
    referencia = SessaoFalsa(REPOS)
    rodar(tmp_path / "ref", referencia)

    interrompida = SessaoFalsa(REPOS, parar_em=len(referencia.pedidos) // 2)
    with pytest.raises(KeyboardInterrupt):
        rodar(tmp_path, interrompida)
    retomada = SessaoFalsa(REPOS)
    rodar(tmp_path, retomada)

    assert interrompida.pedidos + retomada.pedidos == referencia.pedidos
    assert ler(tmp_path / "data/repos.csv") == ler(tmp_path / "ref/data/repos.csv")


def test_marcador_de_outra_janela_e_refeito(tmp_path):
    rodar(tmp_path, SessaoFalsa(REPOS))
    sessao = SessaoFalsa(REPOS)
    api = GitHubAPI("t", tmp_path / "cache", sessao=sessao, dormir=lambda s: None)

    executar(api, ["1000..2000"], INICIO, date(2025, 1, 30), 2, tmp_path / "cache", tmp_path / "data")

    assert any("actions/runs" in url for url, _ in sessao.pedidos)


def test_funil_sem_descartes_pelo_limite():
    resultados = [{"aceito": True, "etapa": None, "motivo": None}]

    funil = montar_funil(1, resultados, limite=5)

    assert funil.linhas[-1] == {"ordem": 6, "etapa": "amostra final (limite 5)", "restantes": 1,
                                "descartados": 0, "motivo": ""}


def test_config_sem_janela_para_com_mensagem(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("janela:\n  inicio:\n  fim:\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="janela.inicio"):
        cli.carregar_config(config)


def test_config_le_datas_da_janela(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("janela:\n  inicio: 2025-01-01\n  fim: '2025-12-31'\n", encoding="utf-8")

    lido = cli.carregar_config(config)

    assert (lido["inicio"], lido["fim"]) == (date(2025, 1, 1), date(2025, 12, 31))

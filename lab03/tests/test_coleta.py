import csv
import json
from datetime import date

import pytest
import requests

from lab03.pipeline import __main__ as cli
from lab03.pipeline.api import GitHubAPI
from lab03.pipeline.coleta import (
    MARCADOR,
    MARCADOR_TRIAGEM,
    MOTIVO_CRIADO_NA_JANELA,
    MOTIVO_NAO_AVALIADO,
    MOTIVO_POUCAS_RELEASES,
    MOTIVO_POUCOS_RUNS,
    criado_na_janela,
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
    def __init__(self, nome, estrelas, actions=True, releases=6, runs=60, criado="2020-01-01T00:00:00Z",
                 runs_na_contagem=None):
        self.nome, self.estrelas, self.actions, self.criado = nome, estrelas, actions, criado
        # v0 fica fora da janela e serve de anterior para a v1
        self.releases = [release("v0", "2024-12-01")] + [
            release(f"v{i}", f"2025-01-{i + 1:02d}") for i in range(1, releases + 1)
        ]
        self.runs = [run(i, "failure" if i % 10 == 0 else "success") for i in range(runs)] + [
            run(1000, "cancelled")
        ]
        # o que o total_count com filtro de status responde; por padrão, o mesmo que a lista
        self.contagem = self.runs if runs_na_contagem is None else [run(i) for i in range(runs_na_contagem)]


class SessaoFalsa:
    """Responde pelo caminho, como o GitHub, e conta as chamadas. `parar_em` simula um Ctrl+C."""

    def __init__(self, repos, parar_em=None):
        self.repos = {r.nome: r for r in repos}
        self.headers = {}
        self.pedidos = []
        self.parar_em = parar_em

    def _busca(self, params):
        filtro = params["q"].split()[0].removeprefix("stars:")
        a, b = (int(filtro[2:]), 10**9) if filtro.startswith(">=") else map(int, filtro.split(".."))
        itens = [{"full_name": r.nome, "stargazers_count": r.estrelas, "created_at": r.criado,
                  "default_branch": "main"}
                 for r in sorted(self.repos.values(), key=lambda r: -r.estrelas) if a <= r.estrelas <= b]
        n, pagina = int(params["per_page"]), int(params["page"])
        return resposta({"total_count": len(itens), "items": itens[(pagina - 1) * n:pagina * n]})

    def get(self, url, params=None, timeout=None):
        if self.parar_em is not None and len(self.pedidos) == self.parar_em:
            raise KeyboardInterrupt
        self.pedidos.append((url, params))
        caminho = url.removeprefix("https://api.github.com")
        if caminho == "/search/repositories":
            return self._busca(params)
        partes = caminho.split("/")
        repo = self.repos["/".join(partes[2:4])]
        resto = "/".join(partes[4:])
        if resto == "":
            return resposta({"stargazers_count": repo.estrelas, "language": "Python",
                             "default_branch": "main", "created_at": repo.criado})
        if resto == "actions/workflows":
            return resposta({"total_count": int(repo.actions)})
        if resto == "contributors":
            return resposta([{"login": "a"}])
        if resto == "releases":
            return resposta(repo.releases)
        if resto.startswith("compare/"):
            commit = {"sha": "c", "commit": {"author": {"date": "2025-01-01T00:00:00Z"}, "message": "m"}}
            return resposta({"total_commits": 1, "commits": [commit], "files": [{"patch": "..."}]})
        if resto == "actions/runs" and "status" in params:
            iguais = [r for r in repo.contagem if r["conclusion"] == params["status"]]
            return resposta({"total_count": len(iguais), "workflow_runs": iguais[:1]})
        if resto == "actions/runs":
            return resposta({"total_count": len(repo.runs), "workflow_runs": repo.runs})
        raise AssertionError(caminho)


REPOS = [
    Repo("o/bom", 1900),
    Repo("o/sem-actions", 1800, actions=False),
    Repo("o/poucas-releases", 1700, releases=3),
    Repo("o/poucos-runs", 1600, runs=40),
    Repo("o/novo", 1550, criado="2025-01-15T09:00:00Z"),
    Repo("o/outro-bom", 1500),
    Repo("o/nem-visto", 1400),
]


def rodar(tmp_path, sessao, limite=2, fim=FIM, so_triagem=False):
    api = GitHubAPI("t", tmp_path / "cache", sessao=sessao, dormir=lambda s: None)
    return executar(api, 1000, INICIO, fim, limite, tmp_path / "cache", tmp_path / "data", so_triagem=so_triagem)


def ler(caminho):
    with open(caminho, encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def resumo(funil):
    return [(l["etapa"], l["restantes"], l["descartados"], l["motivo"]) for l in funil.linhas]


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
    assert not (pasta_repo(tmp_path / "cache", "o/nem-visto") / MARCADOR_TRIAGEM).exists()


def test_funil_fecha_linha_a_linha(tmp_path):
    funil = rodar(tmp_path, SessaoFalsa(REPOS))

    assert resumo(funil) == [
        ("repositórios na busca (>= 1000 estrelas, sem fork e arquivados)", 7, 0, ""),
        ("avaliados em ordem de estrelas", 6, 1, MOTIVO_NAO_AVALIADO),
        ("criados antes do início da janela", 5, 1, MOTIVO_CRIADO_NA_JANELA),
        ("com GitHub Actions", 4, 1, MOTIVO_SEM_ACTIONS),
        ("metadados coletados", 4, 0, ""),
        (">= 5 releases na janela", 3, 1, MOTIVO_POUCAS_RELEASES),
        (">= 50 runs válidos na janela", 2, 1, MOTIVO_POUCOS_RUNS),
        ("compare e runs coletados", 2, 0, ""),
        ("amostra final (limite 2)", 2, 0, ""),
    ]
    for anterior, linha in zip(funil.linhas, funil.linhas[1:]):
        assert linha["restantes"] == anterior["restantes"] - linha["descartados"]


def test_quem_nasceu_na_janela_cai_sem_chamar_a_api(tmp_path):
    sessao = SessaoFalsa(REPOS)
    rodar(tmp_path, sessao)
    assert not [url for url, _ in sessao.pedidos if "/o/novo" in url]


def test_criado_no_meio_do_primeiro_dia_ja_conta_como_dentro():
    assert criado_na_janela("2025-01-01T00:00:01Z", INICIO)
    assert not criado_na_janela("2024-12-31T23:59:59Z", INICIO)


def test_triagem_define_a_amostra_sem_compare_nem_lista_de_runs(tmp_path):
    sessao = SessaoFalsa(REPOS)
    rodar(tmp_path, sessao, so_triagem=True)

    repos = ler(tmp_path / "data/repos.csv")
    assert [(r["repo"], r["releases"], r["runs_validos"]) for r in repos] == [
        ("o/bom", "6", ""), ("o/outro-bom", "6", "")]
    assert (tmp_path / "data/funil.csv").exists()
    assert not (tmp_path / "data/releases.csv").exists()
    assert not [url for url, _ in sessao.pedidos if "/compare/" in url]
    assert all("status" in params for url, params in sessao.pedidos if url.endswith("/actions/runs"))


def test_triagem_e_depois_a_coleta_pesada_reaproveitam_o_que_ja_foi_feito(tmp_path):
    rodar(tmp_path, SessaoFalsa(REPOS), so_triagem=True)
    sessao = SessaoFalsa(REPOS)

    rodar(tmp_path, sessao)

    assert sessao.pedidos and all("/o/bom/" in url or "/o/outro-bom/" in url for url, _ in sessao.pedidos)
    assert not [url for url, _ in sessao.pedidos if "/search/" in url or url.endswith("/releases")]


def test_lista_de_runs_menor_que_a_contagem_tira_o_repo_e_o_funil_continua_fechando(tmp_path):
    repos = [Repo("o/contou-errado", 1950, runs=40, runs_na_contagem=60)] + REPOS
    funil = rodar(tmp_path, SessaoFalsa(repos))

    assert [r["repo"] for r in ler(tmp_path / "data/repos.csv")] == ["o/bom"]
    linhas = {l["etapa"]: l for l in funil.linhas}
    assert linhas[">= 50 runs válidos na janela"]["descartados"] == 1
    assert linhas["amostra final (limite 2)"]["restantes"] == 1
    for anterior, linha in zip(funil.linhas, funil.linhas[1:]):
        assert linha["restantes"] == anterior["restantes"] - linha["descartados"]


def test_segunda_execucao_nao_chama_a_api_alem_da_busca_em_cache(tmp_path):
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

    rodar(tmp_path, sessao, fim=date(2025, 1, 30))

    assert any(url.endswith("/actions/runs") and "status" not in params for url, params in sessao.pedidos)
    assert (pasta_repo(tmp_path / "cache", "o/bom") / MARCADOR).exists()


def test_funil_sem_nao_avaliados_quando_a_busca_acaba_antes():
    resultados = [{"aceito": True, "etapa": None, "motivo": None}]

    funil = montar_funil(1, resultados, limite=5, estrelas_minimas=1000)

    assert funil.linhas[1] == {"ordem": 2, "etapa": "avaliados em ordem de estrelas", "restantes": 1,
                               "descartados": 0, "motivo": ""}
    assert funil.linhas[-1]["restantes"] == 1


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

import base64
import csv
import json
from datetime import date, datetime, timezone

import pytest
import requests

from lab03.metricas.agentes import CAMPOS_ADOCAO
from lab03.pipeline import __main__ as cli
from lab03.pipeline.adocao import Buscador, Falhas, _um_por_pagina, executar, prs_da_busca
from lab03.pipeline.api import ErroAPI, GitHubAPI

INICIO, FIM = date(2026, 1, 1), date(2026, 1, 31)
LINK = '<https://api.github.com/repositories/1/commits?sha=main&page=2>; rel="next"'


def resposta(corpo, status=200, link=None, cabecalhos=None):
    r = requests.Response()
    r.status_code = status
    r._content = json.dumps(corpo).encode()
    r.headers.update({"X-RateLimit-Remaining": "4000", "X-RateLimit-Reset": "0", **(cabecalhos or {})})
    if link:
        r.headers["Link"] = link
    return r


def commit_api(sha, data, mensagem, login="ana", nome="Ana"):
    return {
        "sha": sha,
        "commit": {"author": {"name": nome, "date": data}, "committer": {"date": data}, "message": mensagem},
        "author": {"login": login} if login else None,
        "files": "descartado",
    }


def pr(numero):
    return {"number": numero, "user": {"login": "Copilot"}, "labels": [{"name": "codex"}],
            "created_at": "2026-01-05T00:00:00Z", "pull_request": {"merged_at": None}, "body": "longo"}


COMMITS = {
    "o/ia": [
        [commit_api("c3", "2026-01-20T00:00:00Z", "Fix (#7)"),
         commit_api("c2", "2026-01-10T00:00:00Z", "feat\n\nCo-Authored-By: Claude <noreply@anthropic.com>")],
        [commit_api("c1", "2026-01-02T00:00:00Z", "inicial")],
    ],
    "o/humano": [[commit_api("h1", "2026-01-03T00:00:00Z", "fix: claude não entra")]],
}


class SessaoFalsa:
    """Responde commits, árvore, .gitignore e busca dos dois repos; `falhas` força erros por caminho."""

    def __init__(self, falhas=None):
        self.headers = {}
        self.pedidos = []
        self.falhas = dict(falhas or {})

    def get(self, url, params=None, timeout=None):
        self.pedidos.append((url, params))
        caminho = url.removeprefix("https://api.github.com")
        for trecho, respostas in self.falhas.items():
            if trecho in caminho + str(params) and respostas:
                return respostas.pop(0)
        if caminho == "/search/issues":
            q = params["q"]
            if "o/ia" in q and "head:copilot/" in q:
                return resposta({"total_count": 1, "items": [pr(7)]})
            return resposta({"total_count": 0, "items": []})
        partes = caminho.split("/")
        repo, resto = "/".join(partes[2:4]), "/".join(partes[4:])
        if resto == "commits":
            paginas = COMMITS[repo]
            pagina = int(params.get("page", 1))
            return resposta(paginas[pagina - 1], link=LINK if pagina < len(paginas) else None)
        if resto.startswith("git/trees/"):
            arvore = [{"path": "src/a.py"}, {"path": "CLAUDE.md"}] if repo == "o/ia" else [{"path": "x"}]
            return resposta({"sha": "t", "truncated": False, "tree": arvore})
        if resto == "contents/.gitignore":
            if repo == "o/humano":
                return resposta({"message": "Not Found"}, status=404)
            texto = "node_modules/\n.cursor/\n# AGENTS.md\n"
            return resposta({"content": base64.b64encode(texto.encode()).decode(), "encoding": "base64"})
        raise AssertionError(caminho)


def preparar(tmp_path, repos=("o/ia", "o/humano")):
    pasta = tmp_path / "data"
    pasta.mkdir()
    with (pasta / "repos.csv").open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(["repo", "default_branch", "releases"])
        for repo in repos:
            escritor.writerow([repo, "main", 6])
    return pasta


def rodar(tmp_path, sessao, limite=None):
    api = GitHubAPI("t", tmp_path / "cache", sessao=sessao, dormir=lambda s: None)
    buscador = Buscador(api, dormir=lambda s: None)
    return executar(api, INICIO, FIM, tmp_path / "data", limite, buscador), buscador


def ler(caminho):
    with open(caminho, encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def test_grava_commits_ia_e_acrescenta_colunas_sem_mexer_nas_outras(tmp_path):
    preparar(tmp_path)
    rodar(tmp_path, SessaoFalsa())

    repos = ler(tmp_path / "data/repos.csv")
    assert list(repos[0]) == ["repo", "default_branch", "releases", *CAMPOS_ADOCAO]
    ia, humano = repos
    assert ia["releases"] == "6"
    assert ia["commits_janela"] == "3"
    assert ia["commits_ia"] == "2"
    assert ia["primeiro_commit_ia"] == "2026-01-10T00:00:00Z"
    assert float(ia["proporcao_ia_desde_adocao"]) == 1.0
    assert ia["prs_agente"] == "1"
    assert ia["arquivo_agente"] == "True"
    assert ia["arquivo_agente_gitignore"] == "True"
    assert ia["ferramentas_ia"] == "Claude;Copilot;Cursor"
    assert humano["commits_ia"] == "0"
    assert humano["arquivo_agente"] == "False"
    assert humano["arquivo_agente_gitignore"] == "False"
    assert humano["proporcao_ia_desde_adocao"] == ""

    assert ler(tmp_path / "data/commits_ia.csv") == [
        {"sha": "c3", "repo": "o/ia", "data": "2026-01-20T00:00:00Z", "ferramenta": "Copilot", "familia": "branch"},
        {"sha": "c2", "repo": "o/ia", "data": "2026-01-10T00:00:00Z", "ferramenta": "Claude", "familia": "autoria"},
    ]


def test_cache_guarda_so_o_enxuto_e_a_arvore_e_a_do_ultimo_commit(tmp_path):
    preparar(tmp_path)
    sessao = SessaoFalsa()
    rodar(tmp_path, sessao)

    arvores = [url for url, _ in sessao.pedidos if "/git/trees/" in url]
    assert arvores[0].endswith("/repos/o/ia/git/trees/c3")
    cacheados = [c for p in (tmp_path / "cache/o__ia").glob("commits__*.json")
                 for c in json.loads(p.read_text())["corpo"]]
    assert all(set(c) == {"sha", "data", "autor", "login", "mensagem"} for c in cacheados)
    assert {"sha": "c3", "data": "2026-01-20T00:00:00Z", "autor": "Ana", "login": "ana",
            "mensagem": "Fix (#7)"} in cacheados
    texto_cache = "".join(p.read_text() for p in (tmp_path / "cache").rglob("*.json"))
    assert "descartado" not in texto_cache and "src/a.py" not in texto_cache and "longo" not in texto_cache


def test_segunda_execucao_sai_toda_do_cache(tmp_path):
    preparar(tmp_path)
    rodar(tmp_path, SessaoFalsa())
    antes = (tmp_path / "data/commits_ia.csv").read_text()
    sessao = SessaoFalsa()
    _, buscador = rodar(tmp_path, sessao)
    assert sessao.pedidos == []
    assert buscador.buscas_rede == 0
    assert (tmp_path / "data/commits_ia.csv").read_text() == antes


def test_limite_coleta_so_os_primeiros_e_os_outros_ficam_vazios(tmp_path):
    preparar(tmp_path)
    adocao, buscador = rodar(tmp_path, SessaoFalsa(), limite=1)
    assert list(adocao) == ["o/ia"]
    assert buscador.buscas_rede == 8  # um filtro por prefixo, label e conta bot
    humano = ler(tmp_path / "data/repos.csv")[1]
    assert humano["commits_janela"] == "" and humano["arquivo_agente"] == ""


def test_busca_recusada_deixa_prs_vazio_e_repo_inacessivel_fica_sem_adocao(tmp_path):
    preparar(tmp_path)
    recusa = resposta({"message": "Validation Failed"}, status=422)
    sumido = resposta({"message": "Not Found"}, status=404)
    rodar(tmp_path, SessaoFalsa({"repo:o/ia ": [recusa], "/repos/o/humano/commits": [sumido]}))
    ia, humano = ler(tmp_path / "data/repos.csv")
    assert ia["prs_agente"] == "" and ia["commits_ia"] == "1"
    assert humano["commits_janela"] == "0" and humano["arquivo_agente"] == "False"


def test_erro_4xx_que_nao_e_ausencia_deixa_o_repo_vazio_e_segue(tmp_path):
    preparar(tmp_path)
    proibido = resposta({"message": "Repository access blocked"}, status=403)
    rodar(tmp_path, SessaoFalsa({"/repos/o/ia/commits": [proibido]}))
    ia, humano = ler(tmp_path / "data/repos.csv")
    assert ia["commits_janela"] == ""
    assert humano["commits_janela"] == "1"


def test_falha_de_rede_esgotada_sobe(tmp_path):
    preparar(tmp_path)
    api = GitHubAPI("t", tmp_path / "cache", sessao=SessaoFalsa(), dormir=lambda s: None)

    class Quebrado(Buscador):
        def pagina(self, q, pagina):
            raise ErroAPI("/search/issues", 0, "desisti")

    with pytest.raises(ErroAPI):
        executar(api, INICIO, FIM, tmp_path / "data", None, Quebrado(api))


def test_limite_secundario_da_busca_espera_e_tenta_de_novo(tmp_path):
    preparar(tmp_path, repos=("o/ia",))
    secundario = resposta({"documentation_url": "https://docs.github.com/...#about-secondary-rate-limits",
                           "message": "You have exceeded a secondary rate limit."}, status=403)
    sessao = SessaoFalsa({"/search/issues": [secundario]})
    api = GitHubAPI("t", tmp_path / "cache", sessao=sessao, dormir=lambda s: None)
    esperas = []
    executar(api, INICIO, FIM, tmp_path / "data", None, Buscador(api, dormir=esperas.append))
    assert 60 in esperas
    assert ler(tmp_path / "data/repos.csv")[0]["prs_agente"] == "1"


def test_outro_403_na_busca_nao_e_engolido(tmp_path):
    api = GitHubAPI("t", tmp_path / "cache",
                    sessao=SessaoFalsa({"/search/issues": [resposta({"message": "Forbidden"}, status=403)]}),
                    dormir=lambda s: None)
    with pytest.raises(ErroAPI):
        Buscador(api, dormir=lambda s: None).pagina("repo:o/ia is:pr", 1)


def test_buscador_espaca_as_buscas_de_rede():
    relogio = [100.0]
    esperas = []

    class APIFalsa:
        def arquivo_cache(self, caminho, params):
            return type("Caminho", (), {"exists": lambda self: params["page"] == 3})()

        def get(self, caminho, params, enxugar=None):
            relogio[0] += 0.5
            return {"total_count": 0, "items": []}

    def dormir(s):
        esperas.append(round(s, 2))
        relogio[0] += s

    buscador = Buscador(APIFalsa(), intervalo=2.0, dormir=dormir, agora=lambda: relogio[0])
    for pagina in (1, 2, 3):
        buscador.pagina("q", pagina)
    assert esperas == [1.5]  # a 2ª esperou o resto dos 2 s; a 3ª estava no cache
    assert buscador.buscas_rede == 2


class BuscadorFalso:
    """Busca com `total` PRs por dia da janela, 100 por página, e o teto de 1.000 da API."""

    def __init__(self, por_dia):
        self.por_dia = por_dia
        self.consultas = []

    def pagina(self, q, pagina):
        self.consultas.append((q, pagina))
        a, b = (date.fromisoformat(d) for d in q.split("created:")[1].split(".."))
        total = self.por_dia * ((b - a).days + 1)
        visiveis = min(total, 1000)
        inicio = (pagina - 1) * 100
        itens = [{"number": f"{a}-{i}"} for i in range(inicio, min(inicio + 100, visiveis))]
        return {"total_count": total, "items": itens}


def test_busca_com_mais_de_mil_parte_a_janela_ate_caber():
    buscador = BuscadorFalso(por_dia=40)  # 31 dias -> 1.240, parte em 16 + 15 dias
    itens = prs_da_busca(buscador, "o/r", "head:copilot/", INICIO, FIM)
    assert len(itens) == 1240
    assert {q.split("created:")[1] for q, _ in buscador.consultas} == {
        "2026-01-01..2026-01-31", "2026-01-01..2026-01-16", "2026-01-17..2026-01-31",
    }


def test_busca_pagina_ate_o_total():
    buscador = BuscadorFalso(por_dia=8)  # 248 -> 3 páginas
    assert len(prs_da_busca(buscador, "o/r", "label:codex", INICIO, FIM)) == 248
    assert [p for _, p in buscador.consultas] == [1, 2, 3]


def test_cli_adocao_chama_o_modulo_novo(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text(f"janela:\n  inicio: 2026-01-01\n  fim: 2026-01-31\npasta_saida: {tmp_path / 'data'}\n"
                      f"pasta_cache: {tmp_path / 'cache'}\n")
    chamadas = []
    monkeypatch.setattr(cli.GitHubAPI, "do_ambiente", classmethod(lambda cls, pasta: GitHubAPI(
        "t", pasta, sessao=SessaoFalsa(), dormir=lambda s: None)))
    monkeypatch.setattr(cli.GitHubAPI, "cota", lambda self: {"core": {"remaining": 10}})
    monkeypatch.setattr(cli.adocao, "executar", lambda *args, **kw: chamadas.append((args, kw)))
    assert cli.main(["--config", str(config), "--adocao", "--limite", "5", "--parcial"]) == 0
    assert chamadas[0][0][1:] == (INICIO, FIM, str(tmp_path / "data"), 5)
    assert chamadas[0][1] == {"so_concluidos": True}


def test_mes_com_paginas_demais_e_partido_ate_caber(tmp_path):
    """O /commits dá 500 paginando fundo; acima de 30 páginas o pedaço é partido ao meio."""
    class SessaoFunda(SessaoFalsa):
        def get(self, url, params=None, timeout=None):
            if url.endswith("/commits"):
                self.pedidos.append((url, params))
                a, b = (datetime.fromisoformat(params[k].replace("Z", "+00:00")) for k in ("since", "until"))
                largo = (b - a).days >= 10
                corpo = [commit_api(f"{a:%d}", params["since"], "x")]
                return resposta(corpo, link='<https://x?page=40>; rel="last"' if largo else None)
            return super().get(url, params, timeout)

    preparar(tmp_path, repos=("o/ia",))
    sessao = SessaoFunda()
    rodar(tmp_path, sessao)
    intervalos = [(p["since"][:10], p["until"][:10]) for u, p in sessao.pedidos if u.endswith("/commits")]
    assert intervalos[0] == ("2026-01-01", "2026-01-31")
    assert ("2026-01-01", "2026-01-16") in intervalos and ("2026-01-16", "2026-01-31") in intervalos
    assert int(ler(tmp_path / "data/repos.csv")[0]["commits_janela"]) == 4  # um por pedaço que coube


def test_pedaco_que_da_500_ate_desistir_e_partido_e_o_resto_segue(tmp_path):
    class Sessao500(SessaoFalsa):
        def get(self, url, params=None, timeout=None):
            if url.endswith("/commits") and params.get("since", "").startswith("2026-01-01T00") \
                    and params.get("until", "").startswith("2026-01-31"):
                self.pedidos.append((url, params))
                return resposta({"message": "Server Error"}, status=500)
            return super().get(url, params, timeout)

    preparar(tmp_path, repos=("o/ia",))
    sessao = Sessao500()
    rodar(tmp_path, sessao)
    pedidos = [(p["since"][:10], p["until"][:10]) for u, p in sessao.pedidos if u.endswith("/commits") and "since" in p]
    assert pedidos.count(("2026-01-01", "2026-01-31")) == 5  # as tentativas da GitHubAPI
    assert ("2026-01-01", "2026-01-16") in pedidos and ("2026-01-16", "2026-01-31") in pedidos
    assert ler(tmp_path / "data/repos.csv")[0]["commits_janela"] == "3"


def test_segundo_que_falha_sozinho_vai_um_commit_por_vez_e_conta_o_perdido(tmp_path):
    """O hermes-agent tem um commit que o GitHub não serve: só ele fica de fora."""
    quebrado = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

    class SessaoQuebrada(SessaoFalsa):
        def get(self, url, params=None, timeout=None):
            if url.endswith("/commits") and "since" in params:
                self.pedidos.append((url, params))
                a, b = (datetime.fromisoformat(params[k].replace("Z", "+00:00")) for k in ("since", "until"))
                bom = commit_api(f"{a:%d%H%M%S}", params["since"], "x")
                if not (a <= quebrado <= b):
                    return resposta([bom])
                if int(params["per_page"]) != 1:
                    return resposta({"message": "Server Error"}, status=500)
                vizinhos = {1: [bom], 2: None, 3: [commit_api("viz", params["since"], "y")]}
                pagina = vizinhos.get(int(params["page"]), [])
                return resposta({"message": "x"}, status=500) if pagina is None else resposta(pagina)
            return super().get(url, params, timeout)

    preparar(tmp_path, repos=("o/ia",))
    sessao = SessaoQuebrada()
    rodar(tmp_path, sessao)
    linha = ler(tmp_path / "data/repos.csv")[0]
    assert linha["commits_perdidos"] == "1"
    um_por_vez = [p["page"] for u, p in sessao.pedidos if u.endswith("/commits") and p.get("per_page") == 1]
    assert um_por_vez == [1] + [2] * 5 + [3, 4]  # a página quebrada leva as 5 tentativas

    # retomada sem o marcador do repo: nada que já falhou é tentado de novo
    (tmp_path / "cache/o__ia/_adocao").unlink()
    sessao = SessaoQuebrada()
    rodar(tmp_path, sessao)
    respostas_500 = [p for u, p in sessao.pedidos if u.endswith("/commits")
                     and (p.get("per_page") != 1 or p.get("page") == 2) and "since" in p
                     and datetime.fromisoformat(p["since"].replace("Z", "+00:00")) <= quebrado
                     <= datetime.fromisoformat(p["until"].replace("Z", "+00:00"))]
    assert respostas_500 == []
    assert ler(tmp_path / "data/repos.csv")[0]["commits_perdidos"] == "1"


def test_api_fora_no_um_por_vez_sobe(tmp_path):
    class SessaoFora(SessaoFalsa):
        def get(self, url, params=None, timeout=None):
            if url.endswith("/commits"):
                return resposta({"message": "Server Error"}, status=500)
            return super().get(url, params, timeout)

    preparar(tmp_path, repos=("o/ia",))
    api = GitHubAPI("t", tmp_path / "cache", sessao=SessaoFora(), dormir=lambda s: None)
    with pytest.raises(ErroAPI):
        _um_por_pagina(api, "o/ia", "/repos/o/ia/commits", {"sha": "main", "since": "a", "until": "b"},
                       Falhas(tmp_path / "falhas.json"))


def test_interromper_grava_quem_terminou_e_a_proxima_execucao_continua(tmp_path):
    """Ctrl+C no 2º repo: o 1º já está nos CSVs e não é refeito; o 2º reaproveita o cache."""
    preparar(tmp_path)

    class SessaoCtrlC(SessaoFalsa):
        def get(self, url, params=None, timeout=None):
            if "o/humano" in url and "trees" in url:
                raise KeyboardInterrupt
            return super().get(url, params, timeout)

    with pytest.raises(KeyboardInterrupt):
        rodar(tmp_path, SessaoCtrlC())
    ia, humano = ler(tmp_path / "data/repos.csv")
    assert ia["commits_ia"] == "2" and humano["commits_ia"] == ""
    assert {l["repo"] for l in ler(tmp_path / "data/commits_ia.csv")} == {"o/ia"}

    sessao = SessaoFalsa()
    rodar(tmp_path, sessao)
    caminhos = [url.removeprefix("https://api.github.com") for url, _ in sessao.pedidos]
    assert not any("o/ia" in c or "o%2Fia" in c for c in caminhos)
    assert "/repos/o/humano/commits" not in caminhos  # a página do commits já estava no cache
    assert ler(tmp_path / "data/repos.csv")[1]["commits_ia"] == "0"


def test_parcial_grava_so_os_marcados_sem_chamar_a_api(tmp_path):
    preparar(tmp_path)
    rodar(tmp_path, SessaoFalsa(), limite=1)
    sessao = SessaoFalsa()
    api = GitHubAPI("t", tmp_path / "cache", sessao=sessao, dormir=lambda s: None)
    executar(api, INICIO, FIM, tmp_path / "data", None, Buscador(api), so_concluidos=True)
    assert sessao.pedidos == []
    ia, humano = ler(tmp_path / "data/repos.csv")
    assert ia["commits_ia"] == "2" and humano["commits_janela"] == ""


def test_mudar_as_regras_refaz_o_resultado_so_do_cache(tmp_path, monkeypatch):
    preparar(tmp_path)
    rodar(tmp_path, SessaoFalsa())
    monkeypatch.setattr("lab03.pipeline.adocao.VERSAO_CODIGO", "outra")
    sessao = SessaoFalsa()
    adocao, _ = rodar(tmp_path, sessao)
    assert sessao.pedidos == []
    assert adocao["o/ia"]["commits_ia"] == 2


def test_janela_inteira_completa_o_que_a_fatia_mensal_cortou_cedo(tmp_path):
    """No nvm, o `since` da fatia de setembro parou de andar cedo e perdeu metade dos commits."""
    class SessaoCorte(SessaoFalsa):
        def get(self, url, params=None, timeout=None):
            if url.endswith("/commits"):
                self.pedidos.append((url, params))
                comum = [commit_api("a", "2026-02-10T00:00:00Z", "x")]
                if params["since"].startswith("2026-01-01") and params["until"].startswith("2026-02-28"):
                    return resposta(comum + [commit_api("cortado", "2026-02-03T00:00:00Z", "y")])
                return resposta(comum if params["since"].startswith("2026-02") else [])
            return super().get(url, params, timeout)

    preparar(tmp_path, repos=("o/ia",))
    api = GitHubAPI("t", tmp_path / "cache", sessao=SessaoCorte(), dormir=lambda s: None)
    executar(api, INICIO, date(2026, 2, 28), tmp_path / "data", None, Buscador(api, dormir=lambda s: None))
    assert ler(tmp_path / "data/repos.csv")[0]["commits_janela"] == "2"

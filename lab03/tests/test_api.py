import json

import pytest
import requests

from lab03.pipeline.api import ErroAPI, GitHubAPI, RecursoAusente, links


def resposta(status=200, corpo=None, cabecalhos=None):
    r = requests.Response()
    r.status_code = status
    r._content = b"" if corpo is None else json.dumps(corpo).encode()
    r.headers.update({"X-RateLimit-Remaining": "4000", "X-RateLimit-Reset": "0", **(cabecalhos or {})})
    return r


class SessaoFalsa:
    """Devolve as respostas na ordem e guarda o que foi pedido."""

    def __init__(self, *respostas):
        self.fila = list(respostas)
        self.pedidos = []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.pedidos.append((url, params))
        item = self.fila.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


@pytest.fixture
def esperas():
    return []


def cliente(tmp_path, esperas, *respostas, agora=1000.0):
    sessao = SessaoFalsa(*respostas)
    api = GitHubAPI("t", tmp_path, sessao=sessao, dormir=esperas.append, agora=lambda: agora)
    return api, sessao


def test_segunda_chamada_vem_do_cache(tmp_path, esperas):
    api, sessao = cliente(tmp_path, esperas, resposta(corpo=[{"tag_name": "v1"}]))
    primeira = api.get("/repos/psf/requests/releases")
    segunda = api.get("/repos/psf/requests/releases")
    assert primeira == segunda == [{"tag_name": "v1"}]
    assert len(sessao.pedidos) == 1


def test_cache_sobrevive_a_um_cliente_novo(tmp_path, esperas):
    api, _ = cliente(tmp_path, esperas, resposta(corpo={"default_branch": "main"}))
    api.get("/repos/psf/requests")
    outro, sessao = cliente(tmp_path, esperas)  # fila vazia: se for à rede, quebra
    assert outro.get("/repos/psf/requests") == {"default_branch": "main"}
    assert sessao.pedidos == []


def test_cache_separa_por_repo_e_por_params(tmp_path, esperas):
    api, _ = cliente(tmp_path, esperas)
    a = api.arquivo_cache("/repos/psf/requests/actions/runs", {"created": "2025-01-01..2025-01-31"})
    b = api.arquivo_cache("/repos/psf/requests/actions/runs", {"created": "2025-02-01..2025-02-28"})
    c = api.arquivo_cache("/search/repositories", {"q": "stars:1000..2000"})
    assert a.parent.name == "psf__requests" and a.name.startswith("actions_runs__")
    assert a != b
    assert c.parent.name == "_global"


def test_paginacao_junta_tres_paginas(tmp_path, esperas):
    base = "https://api.github.com/repos/o/r/actions/runs"
    api, sessao = cliente(
        tmp_path,
        esperas,
        resposta(corpo={"workflow_runs": [1, 2]}, cabecalhos={"Link": f'<{base}?per_page=2&page=2>; rel="next"'}),
        resposta(corpo={"workflow_runs": [3, 4]}, cabecalhos={"Link": f'<{base}?per_page=2&page=3>; rel="next"'}),
        resposta(corpo={"workflow_runs": [5]}),
    )
    assert api.paginar("/repos/o/r/actions/runs", {"per_page": 2}, chave="workflow_runs") == [1, 2, 3, 4, 5]
    assert sessao.pedidos[2][1] == {"per_page": "2", "page": "3"}


def test_paginas_seguintes_ficam_na_pasta_do_repo(tmp_path, esperas):
    # o GitHub devolve o next com o id numérico do repo, não com owner/repo
    proxima = {"Link": '<https://api.github.com/repositories/41881900/releases?per_page=100&page=2>; rel="next"'}
    api, sessao = cliente(tmp_path, esperas, resposta(corpo=[1], cabecalhos=proxima), resposta(corpo=[2]))
    assert api.paginar("/repos/microsoft/vscode/releases") == [1, 2]
    assert sessao.pedidos[1][0] == "https://api.github.com/repos/microsoft/vscode/releases"
    assert {p.parent.name for p in tmp_path.rglob("*.json")} == {"microsoft__vscode"}


def test_paginacao_retoma_da_pagina_que_faltou(tmp_path, esperas):
    base = "https://api.github.com/repos/o/r/releases"
    proxima = {"Link": f'<{base}?per_page=100&page=2>; rel="next"'}
    api, _ = cliente(tmp_path, esperas, resposta(corpo=[1], cabecalhos=proxima), KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):  # simula o Ctrl+C na página 2
        api.paginar("/repos/o/r/releases")
    api2, sessao = cliente(tmp_path, esperas, resposta(corpo=[2]))
    assert api2.paginar("/repos/o/r/releases") == [1, 2]
    assert len(sessao.pedidos) == 1  # só a página 2 foi à rede


def test_5xx_repete_com_backoff(tmp_path, esperas):
    api, sessao = cliente(tmp_path, esperas, resposta(502), resposta(502), resposta(corpo={"ok": True}))
    assert api.get("/repos/o/r") == {"ok": True}
    assert len(sessao.pedidos) == 3
    assert esperas == [1, 2]


def test_queda_de_rede_tambem_repete(tmp_path, esperas):
    api, _ = cliente(tmp_path, esperas, requests.ConnectionError("caiu"), resposta(corpo=[]))
    assert api.get("/repos/o/r/tags") == []
    assert esperas == [1]


def test_desiste_depois_do_limite_de_tentativas(tmp_path, esperas):
    api, _ = cliente(tmp_path, esperas, *[resposta(503)] * 5)
    with pytest.raises(ErroAPI):
        api.get("/repos/o/r")
    assert esperas == [1, 2, 4, 8]
    assert not list(tmp_path.rglob("*.json"))  # erro temporário não vai para o cache


def test_cota_zerada_espera_ate_o_reset(tmp_path, esperas):
    zerada = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1600"}
    api, sessao = cliente(tmp_path, esperas, resposta(403, {"message": "API rate limit exceeded"}, zerada),
                          resposta(corpo=[]), agora=1000.0)
    assert api.get("/repos/o/r/releases") == []
    assert esperas == [605]  # 600 s até o reset + 5 de folga
    assert len(sessao.pedidos) == 2


def test_ultima_requisicao_da_cota_faz_a_proxima_esperar(tmp_path, esperas):
    ultima = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1060"}
    api, _ = cliente(tmp_path, esperas, resposta(corpo=[1], cabecalhos=ultima), resposta(corpo=[2]), agora=1000.0)
    api.get("/repos/o/r/releases")
    assert esperas == []
    api.get("/repos/o/r/tags")
    assert esperas == [65]


def test_limite_secundario_respeita_retry_after(tmp_path, esperas):
    api, _ = cliente(tmp_path, esperas, resposta(429, {}, {"Retry-After": "30"}), resposta(corpo=[]))
    api.get("/search/repositories", {"q": "stars:>1000"})
    assert esperas == [30.0]


def test_403_que_nao_e_cota_vira_erro(tmp_path, esperas):
    corpo = {"message": "The history or contributor list is too large to list contributors"}
    api, _ = cliente(tmp_path, esperas, resposta(403, corpo))
    with pytest.raises(ErroAPI) as erro:
        api.get("/repos/torvalds/linux/contributors", {"per_page": 1, "anon": "true"})
    assert erro.value.status == 403
    assert esperas == []


def test_404_levanta_recurso_ausente_e_fica_no_cache(tmp_path, esperas):
    api, sessao = cliente(tmp_path, esperas, resposta(404, {"message": "Not Found"}))
    for _ in range(2):
        with pytest.raises(RecursoAusente) as erro:
            api.get("/repos/o/r/compare/v1.0...v1.1")
        assert erro.value.status == 404
    assert len(sessao.pedidos) == 1


def test_ultima_pagina_le_o_link(tmp_path, esperas):
    link = '<https://api.github.com/repositories/1/contributors?per_page=1&anon=true&page=2>; rel="next", ' \
           '<https://api.github.com/repositories/1/contributors?per_page=1&anon=true&page=347>; rel="last"'
    api, _ = cliente(tmp_path, esperas, resposta(corpo=[{}], cabecalhos={"Link": link}))
    assert api.ultima_pagina("/repos/o/r/contributors", {"per_page": 1, "anon": "true"}) == 347


def test_ultima_pagina_sem_link_conta_a_lista(tmp_path, esperas):
    api, _ = cliente(tmp_path, esperas, resposta(corpo=[{"login": "sozinho"}]))
    assert api.ultima_pagina("/repos/o/r/contributors", {"per_page": 1}) == 1


def test_json_corrompido_no_cache_e_refeito(tmp_path, esperas):
    api, sessao = cliente(tmp_path, esperas, resposta(corpo={"v": 2}))
    arquivo = api.arquivo_cache("/repos/o/r", None)
    arquivo.parent.mkdir(parents=True)
    arquivo.write_text('{"status": 200, "co')
    assert api.get("/repos/o/r") == {"v": 2}
    assert len(sessao.pedidos) == 1


def test_links_entende_varios_rels():
    cab = '<https://x/a?page=2>; rel="next", <https://x/a?page=9>; rel="last"'
    assert links(cab) == {"next": "https://x/a?page=2", "last": "https://x/a?page=9"}
    assert links(None) == {}


def test_sem_token_no_ambiente(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr("lab03.pipeline.api.load_dotenv", lambda: None)
    with pytest.raises(SystemExit):
        GitHubAPI.do_ambiente(tmp_path)

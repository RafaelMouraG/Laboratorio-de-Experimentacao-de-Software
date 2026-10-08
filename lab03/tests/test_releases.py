import pytest

from lab03.pipeline.api import RecursoAusente
from lab03.pipeline.releases import (
    coletar,
    commits_da_release,
    data_da_tag,
    listar_releases,
    listar_tags,
    release_anterior,
    releases_na_janela,
)


def release(tag, publicada, draft=False, pre=False):
    return {
        "tag_name": tag, "published_at": publicada, "draft": draft, "prerelease": pre,
        "html_url": f"https://github.com/o/r/releases/tag/{tag}", "body": "descartado",
    }


def commit(sha, data, mensagem="feat: algo"):
    return {"sha": sha, "commit": {"author": {"date": data}, "message": mensagem}, "url": "descartado"}


class APIFalsa:
    """Responde `paginar` e `get` a partir de dicionários montados no teste."""

    def __init__(self, releases=(), compares=None, tags=(), commits=None):
        self.releases = list(releases)
        self.compares = compares or {}  # "base...head" -> lista de commits
        self.tags = list(tags)
        self.commits = commits or {}  # sha -> committer date
        self.pedidos = []

    def paginar(self, caminho, params=None, chave=None):
        self.pedidos.append((caminho, params))
        if caminho.endswith("/releases"):
            return self.releases
        if caminho.endswith("/tags"):
            return self.tags
        raise AssertionError(caminho)

    def get(self, caminho, params=None):
        self.pedidos.append((caminho, params))
        if "/compare/" in caminho:
            intervalo = caminho.split("/compare/")[1]
            if intervalo not in self.compares:
                raise RecursoAusente(caminho, 404)
            todos = self.compares[intervalo]
            n, pagina = params["per_page"], params["page"]
            return {"total_commits": len(todos), "commits": todos[(pagina - 1) * n:pagina * n]}
        if "/commits/" in caminho:
            sha = caminho.rsplit("/", 1)[1]
            if sha not in self.commits:
                raise RecursoAusente(caminho, 404)
            return {"commit": {"committer": {"date": self.commits[sha]}}}
        raise AssertionError(caminho)


def test_drafts_saem_e_a_lista_fica_em_ordem_de_publicacao():
    api = APIFalsa([
        release("v3", "2025-03-01T00:00:00Z"),
        release("v4-rascunho", None, draft=True),
        release("v1", "2025-01-01T00:00:00Z"),
        release("v2", "2025-02-01T00:00:00Z", draft=True),
    ])
    releases = listar_releases(api, "o/r")
    assert [r["tag_name"] for r in releases] == ["v1", "v3"]
    assert set(releases[0]) == {"tag_name", "published_at", "prerelease", "html_url"}


def test_janela_inclui_as_pontas_e_tira_pre_release_por_padrao():
    releases = [
        {"tag_name": "a", "published_at": "2024-12-31T23:59:59Z", "prerelease": False},
        {"tag_name": "b", "published_at": "2025-01-01T00:00:00Z", "prerelease": False},
        {"tag_name": "c", "published_at": "2025-06-01T12:00:00Z", "prerelease": True},
        {"tag_name": "d", "published_at": "2025-12-31T23:59:59Z", "prerelease": False},
        {"tag_name": "e", "published_at": "2026-01-01T00:00:00Z", "prerelease": False},
    ]
    assert [r["tag_name"] for r in releases_na_janela(releases, "2025-01-01", "2025-12-31")] == ["b", "d"]
    com_pre = releases_na_janela(releases, "2025-01-01", "2025-12-31", com_pre=True)
    assert [r["tag_name"] for r in com_pre] == ["b", "c", "d"]


def test_anterior_pula_pre_release_e_primeira_nao_tem_anterior():
    releases = [
        {"tag_name": "v1", "prerelease": False},
        {"tag_name": "v2-rc1", "prerelease": True},
        {"tag_name": "v2", "prerelease": False},
    ]
    assert release_anterior(releases, releases[2])["tag_name"] == "v1"
    assert release_anterior(releases, releases[1])["tag_name"] == "v1"
    assert release_anterior(releases, releases[0]) is None


def test_compare_com_tres_paginas_junta_todos_os_commits():
    todos = [commit(f"s{i}", f"2025-01-01T00:{i % 60:02d}:00Z") for i in range(260)]
    api = APIFalsa(compares={"v1...v2": todos})
    commits = commits_da_release(api, "o/r", "v1", "v2")
    assert len(commits) == 260
    assert [p[1]["page"] for p in api.pedidos] == [1, 2, 3]
    assert commits[0] == {"sha": "s0", "data": "2025-01-01T00:00:00Z", "mensagem": "feat: algo"}


def test_commit_guarda_so_a_primeira_linha_da_mensagem():
    api = APIFalsa(compares={"v1...v2": [commit("a", "2025-01-01T00:00:00Z", "fix: trava\n\ncorpo longo")]})
    assert commits_da_release(api, "o/r", "v1", "v2")[0]["mensagem"] == "fix: trava"


def test_compare_vazio_para_na_primeira_pagina():
    api = APIFalsa(compares={"v1...v2": []})
    assert commits_da_release(api, "o/r", "v1", "v2") == []
    assert len(api.pedidos) == 1


def test_tag_com_barra_vai_codificada_no_compare():
    api = APIFalsa(compares={"pkg%2Fv1...pkg%2Fv2": []})
    commits_da_release(api, "o/r", "pkg/v1", "pkg/v2")
    assert api.pedidos[0][0] == "/repos/o/r/compare/pkg%2Fv1...pkg%2Fv2"


def test_anterior_fora_da_janela_entra_no_compare():
    api = APIFalsa(
        releases=[release("v1", "2024-11-01T00:00:00Z"), release("v2", "2025-02-01T00:00:00Z")],
        compares={"v1...v2": [commit("a", "2025-01-20T00:00:00Z")]},
    )
    resultado = coletar(api, "o/r", "2025-01-01", "2025-12-31")
    assert [r["tag_name"] for r in resultado["releases"]] == ["v2"]
    v2 = resultado["releases"][0]
    assert v2["commits"][0]["sha"] == "a"
    assert v2["sem_anterior"] is False


def test_primeira_release_da_historia_fica_sem_anterior_e_sem_compare():
    api = APIFalsa(releases=[release("v1", "2025-02-01T00:00:00Z")])
    v1 = coletar(api, "o/r", "2025-01-01", "2025-12-31")["releases"][0]
    assert v1["sem_anterior"] is True and v1["commits"] == []
    assert not any("/compare/" in p[0] for p in api.pedidos)


def test_compare_404_marca_a_release_e_segue():
    api = APIFalsa(
        releases=[release("v1", "2025-01-01T00:00:00Z"), release("v2", "2025-02-01T00:00:00Z"),
                  release("v3", "2025-03-01T00:00:00Z")],
        compares={"v2...v3": [commit("b", "2025-02-15T00:00:00Z")]},  # v1...v2 não existe
    )
    resultado = coletar(api, "o/r", "2025-01-01", "2025-12-31")
    v1, v2, v3 = resultado["releases"]
    assert v2["ignorada_compare_404"] is True and v2["commits"] == []
    assert v3["ignorada_compare_404"] is False and len(v3["commits"]) == 1
    assert resultado["ignoradas_compare_404"] == 1


def test_tags_so_sao_coletadas_quando_pedidas():
    api = APIFalsa(releases=[release("v1", "2025-02-01T00:00:00Z")])
    assert coletar(api, "o/r", "2025-01-01", "2025-12-31")["tags"] is None
    assert not any(p[0].endswith("/tags") for p in api.pedidos)


def test_tags_ganham_a_data_do_commit_e_saem_ordenadas():
    api = APIFalsa(
        tags=[{"name": "v2", "commit": {"sha": "b"}}, {"name": "v1", "commit": {"sha": "a"}},
              {"name": "orfa", "commit": {"sha": "sumiu"}}],
        commits={"a": "2025-01-01T10:00:00Z", "b": "2025-03-01T10:00:00Z"},
    )
    tags = coletar(api, "o/r", "2025-01-01", "2025-12-31", coletar_tags=True)["tags"]
    assert tags == [
        {"nome": "v1", "sha": "a", "data": "2025-01-01T10:00:00Z"},
        {"nome": "v2", "sha": "b", "data": "2025-03-01T10:00:00Z"},
    ]


def test_listar_tags_e_data_da_tag():
    api = APIFalsa(tags=[{"name": "v1", "commit": {"sha": "a"}}], commits={"a": "2025-01-01T10:00:00Z"})
    assert listar_tags(api, "o/r") == [{"nome": "v1", "sha": "a"}]
    assert data_da_tag(api, "o/r", "a") == "2025-01-01T10:00:00Z"
    with pytest.raises(RecursoAusente):
        data_da_tag(api, "o/r", "nao-existe")

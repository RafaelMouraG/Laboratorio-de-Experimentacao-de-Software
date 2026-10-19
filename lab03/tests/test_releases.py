import pytest

from lab03.pipeline.api import RecursoAusente
from lab03.pipeline.releases import (
    _compare_enxuto,
    coletar,
    commits_da_release,
    entregas_por_tag,
    listar_releases,
    listar_tags,
    release_anterior,
    releases_na_janela,
)


def release(tag, publicada, draft=False, pre=False):
    return {
        "tag_name": tag, "published_at": publicada, "draft": draft, "prerelease": pre,
        "html_url": f"https://github.com/o/r/releases/tag/{tag}", "body": f"notas da {tag}",
        "author": "descartado",
    }


def commit(sha, data, mensagem="feat: algo"):
    return {"sha": sha, "commit": {"author": {"date": data}, "message": mensagem}, "url": "descartado"}


class APIFalsa:
    """Responde `paginar` e `get` a partir de dicionários montados no teste."""

    def __init__(self, releases=(), compares=None, tags=()):
        self.releases = list(releases)
        self.compares = compares or {}  # "base...head" -> lista de commits
        self.tags = list(tags)  # nós de `refs` da GraphQL, já do mais novo para o mais velho
        self.pedidos = []

    def paginar(self, caminho, params=None, chave=None):
        self.pedidos.append((caminho, params))
        if caminho.endswith("/releases"):
            return self.releases
        raise AssertionError(caminho)

    def graphql(self, consulta, variaveis):
        """Páginas de 2 tags, para os testes passarem por mais de uma."""
        self.pedidos.append(("graphql", variaveis))
        inicio = int(variaveis["depois"] or 0)
        fim = inicio + 2
        return {"repository": {"refs": {
            "pageInfo": {"hasNextPage": fim < len(self.tags), "endCursor": str(fim)},
            "nodes": self.tags[inicio:fim],
        }}}

    def get(self, caminho, params=None, enxugar=None):
        self.pedidos.append((caminho, params))
        if "/compare/" in caminho:
            intervalo = caminho.split("/compare/")[1]
            if intervalo not in self.compares:
                raise RecursoAusente(caminho, 404)
            todos = self.compares[intervalo]
            n, pagina = params["per_page"], params["page"]
            corpo = {"total_commits": len(todos), "commits": todos[(pagina - 1) * n:pagina * n],
                     "files": [{"patch": "@@ diff enorme @@"}]}
            return enxugar(corpo) if enxugar else corpo
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
    assert set(releases[0]) == {"tag_name", "published_at", "prerelease", "html_url", "body"}
    assert releases[0]["body"] == "notas da v1"


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


def test_com_pre_a_anterior_pode_ser_pre_release():
    releases = [
        {"tag_name": "v1", "prerelease": False},
        {"tag_name": "v2-rc1", "prerelease": True},
        {"tag_name": "v2", "prerelease": False},
    ]
    assert release_anterior(releases, releases[2], com_pre=True)["tag_name"] == "v2-rc1"
    assert release_anterior(releases, releases[1], com_pre=True)["tag_name"] == "v1"


def test_coleta_com_pre_compara_com_a_pre_release_anterior():
    api = APIFalsa(
        releases=[release("v1", "2025-01-01T00:00:00Z"), release("v2-rc1", "2025-02-01T00:00:00Z", pre=True),
                  release("v2", "2025-03-01T00:00:00Z")],
        compares={"v1...v2-rc1": [commit("a", "2025-01-20T00:00:00Z")],
                  "v2-rc1...v2": [commit("b", "2025-02-20T00:00:00Z")]},
    )
    principal = coletar(api, "o/r", "2025-01-01", "2025-12-31")["releases"]
    assert [r["tag_name"] for r in principal] == ["v1", "v2"]
    com_pre = coletar(api, "o/r", "2025-01-01", "2025-12-31", com_pre=True)["releases"]
    assert [r["tag_name"] for r in com_pre] == ["v1", "v2-rc1", "v2"]
    assert [c["sha"] for c in com_pre[2]["commits"]] == ["b"]


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


def test_cache_do_compare_fica_so_com_o_que_o_pipeline_le():
    corpo = {"total_commits": 1, "files": [{"patch": "@@ diff @@"}],
             "commits": [commit("a", "2025-01-01T00:00:00Z", "fix: trava\n\ncorpo longo")]}
    enxuto = _compare_enxuto(corpo)
    assert enxuto == {"total_commits": 1, "commits": [
        {"sha": "a", "commit": {"author": {"date": "2025-01-01T00:00:00Z"}, "message": "fix: trava"}}]}
    assert _compare_enxuto(enxuto) == enxuto


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


def leve(nome, sha, data):
    return {"name": nome, "target": {"__typename": "Commit", "oid": sha, "committedDate": data}}


def anotada(nome, sha, data):
    return {"name": nome, "target": {"__typename": "Tag", "target": {
        "__typename": "Commit", "oid": sha, "committedDate": data}}}


def test_tags_so_sao_coletadas_quando_pedidas():
    api = APIFalsa(releases=[release("v1", "2025-02-01T00:00:00Z")])
    assert coletar(api, "o/r", "2025-01-01", "2025-12-31")["tags"] is None
    assert not any(p[0] == "graphql" for p in api.pedidos)


def test_tag_leve_e_anotada_ganham_a_data_do_commit_e_saem_ordenadas():
    api = APIFalsa(tags=[
        anotada("v2", "b", "2025-03-01T10:00:00Z"),
        {"name": "arvore", "target": {"__typename": "Tree", "oid": "t"}},
        leve("v1", "a", "2025-01-01T10:00:00Z"),
    ])
    assert listar_tags(api, "o/r") == [
        {"nome": "v1", "sha": "a", "data": "2025-01-01T10:00:00Z"},
        {"nome": "v2", "sha": "b", "data": "2025-03-01T10:00:00Z"},
    ]
    assert sum(p[0] == "graphql" for p in api.pedidos) == 2


def test_tag_anotada_que_aponta_para_outra_tag_chega_no_commit():
    dupla = {"name": "v3", "target": {"__typename": "Tag", "target": anotada("x", "c", "2025-04-01T00:00:00Z")["target"]}}
    api = APIFalsa(tags=[dupla])
    assert listar_tags(api, "o/r") == [{"nome": "v3", "sha": "c", "data": "2025-04-01T00:00:00Z"}]


def test_listagem_para_na_primeira_pagina_que_passa_do_inicio():
    api = APIFalsa(tags=[
        leve("v4", "d", "2025-04-01T00:00:00Z"), leve("v3", "c", "2024-12-01T00:00:00Z"),
        leve("v2", "b", "2024-06-01T00:00:00Z"), leve("v1", "a", "2024-01-01T00:00:00Z"),
    ])
    tags = listar_tags(api, "o/r", desde="2025-01-01")
    assert [t["nome"] for t in tags] == ["v3", "v4"]
    assert sum(p[0] == "graphql" for p in api.pedidos) == 1


def test_entregas_por_tag_usam_a_tag_anterior_mesmo_fora_da_janela():
    api = APIFalsa(
        tags=[leve("v3", "c", "2025-03-01T00:00:00Z"), leve("v2", "b", "2025-02-01T00:00:00Z"),
              leve("v1", "a", "2024-12-01T00:00:00Z")],
        compares={"v1...v2": [commit("x", "2025-01-15T00:00:00Z")], "v2...v3": [commit("y", "2025-02-15T00:00:00Z")]},
    )
    entregas = entregas_por_tag(api, "o/r", "2025-01-01", "2025-12-31")
    assert [e["tag_name"] for e in entregas] == ["v2", "v3"]
    assert entregas[0]["published_at"] == "2025-02-01T00:00:00Z"
    assert [c["sha"] for c in entregas[0]["commits"]] == ["x"]
    assert entregas[0]["sem_anterior"] is False and entregas[0]["body"] is None


def test_tags_no_mesmo_commit_sao_uma_entrega_so():
    api = APIFalsa(
        tags=[leve("pkg-b@1.0", "b", "2025-02-01T00:00:00Z"), leve("pkg-a@1.0", "b", "2025-02-01T00:00:00Z"),
              leve("v0", "a", "2024-12-01T00:00:00Z")],
        compares={"v0...pkg-a%401.0": [commit("x", "2025-01-15T00:00:00Z")]},
    )
    entregas = entregas_por_tag(api, "o/r", "2025-01-01", "2025-12-31")
    assert [e["tag_name"] for e in entregas] == ["pkg-a@1.0"]


def test_primeira_tag_da_historia_fica_sem_anterior_e_compare_404_segue():
    api = APIFalsa(tags=[leve("v2", "b", "2025-02-01T00:00:00Z"), leve("v1", "a", "2025-01-10T00:00:00Z")])
    v1, v2 = entregas_por_tag(api, "o/r", "2025-01-01", "2025-12-31")
    assert v1["sem_anterior"] is True and v1["commits"] == []
    assert v2["ignorada_compare_404"] is True


def test_filtro_tambem_vale_para_a_tag_anterior():
    api = APIFalsa(
        tags=[leve("v1.1", "c", "2025-03-01T00:00:00Z"), leve("ciflow/trunk/9", "b", "2024-12-20T00:00:00Z"),
              leve("v1.0", "a", "2024-12-01T00:00:00Z")],
        compares={"v1.0...v1.1": [commit("x", "2025-02-01T00:00:00Z")]},
    )
    [entrega] = entregas_por_tag(api, "o/r", "2025-01-01", "2025-12-31", filtro=lambda nome: "/" not in nome)
    assert entrega["tag_name"] == "v1.1" and [c["sha"] for c in entrega["commits"]] == ["x"]
    assert sum(p[0] == "graphql" for p in api.pedidos) == 2  # a 1ª página só tinha a tag de CI antes da janela

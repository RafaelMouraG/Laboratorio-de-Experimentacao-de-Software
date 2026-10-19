import csv
from datetime import date

from lab03.pipeline.alternativas import executar, repos_da_amostra
from lab03.pipeline.api import RecursoAusente
from lab03.tests.test_releases import APIFalsa, commit, leve, release


class APIContada(APIFalsa):
    """A `APIFalsa` dos testes de releases com o contador que o `executar` lê."""

    chamadas_rede = 0
    restante = None


class APISumida(APIContada):
    def paginar(self, caminho, params=None, chave=None):
        raise RecursoAusente(caminho, 404)


def api_com_dados():
    return APIContada(
        releases=[release("v1", "2025-01-01T00:00:00Z"), release("v2-rc1", "2025-02-01T00:00:00Z", pre=True),
                  release("v2", "2025-03-01T00:00:00Z")],
        compares={"v1...v2-rc1": [commit("a", "2025-01-20T00:00:00Z")],
                  "v2-rc1...v2": [commit("b", "2025-02-20T00:00:00Z"), commit("c", "2025-02-21T00:00:00Z")],
                  "v1...v2": [commit("a", "2025-01-20T00:00:00Z")]},
        tags=[leve("v2", "s2", "2025-02-28T00:00:00Z"), leve("v1", "s1", "2024-12-31T00:00:00Z")],
    )


def ler(caminho):
    with open(caminho, encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def test_grava_as_duas_unidades_e_reaproveita_o_marcador(tmp_path):
    (tmp_path / "repos.csv").write_text("repo,estrelas\no/r,10\n", encoding="utf-8")
    inicio, fim = date(2025, 1, 1), date(2025, 12, 31)
    executar(api_com_dados(), repos_da_amostra(tmp_path), inicio, fim, tmp_path / "cache", tmp_path)

    pre = ler(tmp_path / "releases_pre.csv")
    assert [(r["tag_name"], r["prerelease"], r["commits"]) for r in pre] == [
        ("v1", "False", "0"), ("v2-rc1", "True", "1"), ("v2", "False", "2")]
    tags = ler(tmp_path / "tags.csv")
    assert [(t["tag_name"], t["sha"], t["commits"], t["sem_anterior"]) for t in tags] == [("v2", "s2", "1", "False")]

    vazia = APIContada()  # sem dados: se o marcador não for lido, os CSVs saem vazios
    executar(vazia, ["o/r"], inicio, fim, tmp_path / "cache", tmp_path)
    assert vazia.pedidos == []
    assert len(ler(tmp_path / "releases_pre.csv")) == 3


def test_uma_unidade_so_nao_toca_na_outra(tmp_path):
    inicio, fim = date(2025, 1, 1), date(2025, 12, 31)
    api = api_com_dados()
    executar(api, ["o/r"], inicio, fim, tmp_path / "cache", tmp_path, unidades=("pre",))
    assert not any(p[0] == "graphql" for p in api.pedidos)
    assert (tmp_path / "releases_pre.csv").exists() and not (tmp_path / "tags.csv").exists()


def test_repo_que_sumiu_fica_sem_linhas_e_sem_marcador(tmp_path):
    inicio, fim = date(2025, 1, 1), date(2025, 12, 31)
    [resultado] = executar(APISumida(), ["o/r"], inicio, fim, tmp_path / "cache", tmp_path, ("pre",))["pre"]
    assert resultado["erro"] and resultado["entregas"] == []
    assert not (tmp_path / "cache" / "o__r" / "_alternativas_pre").exists()
    assert ler(tmp_path / "releases_pre.csv") == []


def test_tags_de_versao_deixam_de_fora_as_de_ci(tmp_path):
    api = APIContada(
        tags=[leve("ciflow/trunk/7", "s3", "2025-03-01T00:00:00Z"), leve("v2", "s2", "2025-02-28T00:00:00Z"),
              leve("v1.0", "s1", "2024-12-31T00:00:00Z")],
        compares={"v1.0...v2": []},
    )
    inicio, fim = date(2025, 1, 1), date(2025, 12, 31)
    [resultado] = executar(api, ["o/r"], inicio, fim, tmp_path / "cache", tmp_path, ("tag",), tags_de_versao=True)["tag"]
    assert resultado["entregas"] == []  # `v2` não tem X.Y e `ciflow/trunk/7` é de CI

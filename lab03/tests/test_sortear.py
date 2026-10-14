import csv
import gzip
import json

import pandas as pd

from lab03.pipeline.api import RecursoAusente
from lab03.validacao.sortear import (
    CAMPOS_ROTULO_RELEASES,
    CAMPOS_ROTULO_REPOS,
    gravar,
    sortear_releases,
    sortear_repos,
    url_compare,
)


def release(tag, dia, pre=False):
    return {"tag_name": tag, "published_at": f"2025-{dia}T12:00:00Z", "draft": False, "prerelease": pre,
            "html_url": f"https://github.com/o/r/releases/tag/{tag}", "body": f"notas da {tag}"}


class APIFalsa:
    """Releases e compares de um repo só; `sem_compare` lista os pares que dão 404."""

    def __init__(self, lista, sem_compare=()):
        self.lista = lista
        self.sem_compare = set(sem_compare)

    def paginar(self, caminho, params=None, chave=None):
        return self.lista

    def get(self, caminho, params=None, enxugar=None):
        par = caminho.split("/compare/")[1]
        if par in self.sem_compare:
            raise RecursoAusente(caminho, 404)
        commit = {"sha": par, "commit": {"author": {"date": "2025-01-01T00:00:00Z"}, "message": f"fix: {par}"}}
        return {"total_commits": 1, "commits": [commit]}


# v0 é a primeira da história (fora da janela); v1..v9 dentro, mais uma pré-release
LISTA = [release("v0", "01-01")] + [release(f"v{i}", f"0{i}-15") for i in range(1, 10)] + [
    release("v9.1-rc1", "09-20", pre=True)]


def sorteio(api, **kwargs):
    return sortear_releases(api, "o/r", "2025-02-01", "2025-12-31", **kwargs)


def test_mesma_semente_mesmo_sorteio_de_repos():
    repos = pd.DataFrame({"repo": [f"o/r{i:03d}" for i in range(300)], "estrelas": range(300),
                          "linguagem": ["Go"] * 300})
    a, b = sortear_repos(repos), sortear_repos(repos)
    assert list(a["repo"]) == list(b["repo"])
    assert len(a) == 60 and a["repo"].is_unique
    assert list(sortear_repos(repos, semente=7)["repo"]) != list(a["repo"])


def test_amostra_menor_que_60_entra_inteira():
    repos = pd.DataFrame({"repo": ["o/b", "o/a"], "estrelas": [1, 2], "linguagem": ["Go", "Go"]})
    assert list(sortear_repos(repos)["repo"]) == ["o/a", "o/b"]


def test_cinco_releases_reproduziveis_e_em_ordem_de_data():
    a, b = sorteio(APIFalsa(LISTA)), sorteio(APIFalsa(LISTA))
    assert [r["tag_name"] for r in a] == [r["tag_name"] for r in b]
    assert len(a) == 5
    assert [r["published_at"] for r in a] == sorted(r["published_at"] for r in a)


def test_pre_release_e_release_sem_anterior_nunca_saem():
    # v1 é a primeira da história, então não tem anterior para o compare
    lista = [release("v1", "03-01"), release("v1.1-rc", "03-05", pre=True), release("v2", "04-01"),
             release("v3", "05-01")]
    tags = {r["tag_name"] for r in sortear_releases(APIFalsa(lista), "o/r", "2025-01-01", "2025-12-31")}
    assert tags == {"v2", "v3"}


def test_compare_que_nao_existe_e_trocado_por_outra_release():
    antes = sorteio(APIFalsa(LISTA))
    bloqueado = f"{antes[0]['anterior']['tag_name']}...{antes[0]['tag_name']}"
    depois = sorteio(APIFalsa(LISTA, sem_compare=[bloqueado]))
    assert len(depois) == 5
    assert antes[0]["tag_name"] not in {r["tag_name"] for r in depois}
    assert len({r["tag_name"] for r in antes} & {r["tag_name"] for r in depois}) == 4


def test_release_sorteada_leva_o_que_a_heuristica_le():
    r = sorteio(APIFalsa(LISTA), n=1)[0]
    anterior = r["anterior"]["tag_name"]
    assert r["notas"] == f"notas da {r['tag_name']}"
    assert r["commits"] == [{"sha": f"{anterior}...{r['tag_name']}", "data": "2025-01-01T00:00:00Z",
                             "mensagem": f"fix: {anterior}...{r['tag_name']}"}]
    assert r["url_compare"] == f"https://github.com/o/r/compare/{anterior}...{r['tag_name']}"


def test_url_compare_codifica_tag_com_barra():
    assert url_compare("o/r", "pkg/v1", "pkg/v2") == "https://github.com/o/r/compare/pkg%2Fv1...pkg%2Fv2"


def ler(caminho):
    with open(caminho, encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def gravar_exemplo(pasta):
    amostra = pd.DataFrame({"repo": ["o/r"], "estrelas": [1500], "linguagem": [None]})
    return gravar(pasta, amostra, sorteio(APIFalsa(LISTA)), avaliadores=("ana", "bia"))


def test_planilhas_iguais_entre_avaliadores_e_com_rotulos_vazios(tmp_path):
    gravar_exemplo(tmp_path)

    assert ler(tmp_path / "rotulos/ana_repos.csv") == ler(tmp_path / "rotulos/bia_repos.csv")
    assert ler(tmp_path / "rotulos/ana_releases.csv") == ler(tmp_path / "rotulos/bia_releases.csv")
    repos = ler(tmp_path / "rotulos/ana_repos.csv")
    assert list(repos[0]) == list(CAMPOS_ROTULO_REPOS)
    assert (repos[0]["tipo_projeto"], repos[0]["entregas_reais"]) == ("", "")
    releases = ler(tmp_path / "rotulos/ana_releases.csv")
    assert list(releases[0]) == list(CAMPOS_ROTULO_RELEASES)
    assert len(releases) == 5 and {r["corretiva"] for r in releases} == {""}
    assert ler(tmp_path / "amostra_ouro_repos.csv")[0]["linguagem"] == ""


def test_entrada_da_heuristica_fica_fora_das_planilhas(tmp_path):
    gravar_exemplo(tmp_path)

    with gzip.open(tmp_path / "heuristica_entrada.jsonl.gz", "rt", encoding="utf-8") as arquivo:
        linhas = [json.loads(l) for l in arquivo]
    assert len(linhas) == 5
    assert set(linhas[0]) == {"repo", "tag_name", "published_at", "notas", "anterior", "commits"}
    assert "notas" not in ler(tmp_path / "rotulos/ana_releases.csv")[0]


def test_mesmo_sorteio_gera_o_mesmo_arquivo(tmp_path):
    gravar_exemplo(tmp_path / "a")
    gravar_exemplo(tmp_path / "b")
    for nome in ("heuristica_entrada.jsonl.gz", "amostra_ouro_releases.csv", "rotulos/ana_releases.csv"):
        assert (tmp_path / "a" / nome).read_bytes() == (tmp_path / "b" / nome).read_bytes()


def test_rodar_de_novo_nao_apaga_planilha_ja_rotulada(tmp_path):
    gravar_exemplo(tmp_path)
    planilha = tmp_path / "rotulos/ana_repos.csv"
    rotulada = planilha.read_text().replace("https://github.com/o/r,,", "https://github.com/o/r,cli,sim")
    planilha.write_text(rotulada)

    mantidas = gravar_exemplo(tmp_path)

    assert planilha.read_text() == rotulada
    assert set(mantidas) == set((tmp_path / "rotulos").iterdir())

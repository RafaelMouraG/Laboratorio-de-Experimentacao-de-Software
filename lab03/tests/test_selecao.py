import csv
import logging
from itertools import islice

from lab03.pipeline.selecao import (
    MOTIVO_SEM_ACTIONS,
    TETO_BUSCA,
    Funil,
    candidatos_por_estrelas,
    total_na_busca,
    usa_actions,
)


class BuscaFalsa:
    """Simula o /search/repositories: filtra pelo `stars:` da query, ordena e corta em 1000."""

    def __init__(self, estrelas_por_repo):
        self.repos = sorted(estrelas_por_repo.items(), key=lambda par: (-par[1], par[0]))
        self.consultas = []

    def get(self, caminho, params):
        assert caminho == "/search/repositories"
        assert (params["sort"], params["order"]) == ("stars", "desc")
        self.consultas.append(dict(params))
        filtro = params["q"].split()[0].removeprefix("stars:")
        if filtro.startswith(">="):
            a, b = int(filtro[2:]), float("inf")
        else:
            a, b = map(int, filtro.split(".."))
        achados = [{"full_name": nome, "stargazers_count": e} for nome, e in self.repos if a <= e <= b]
        n, pagina = params["per_page"], params["page"]
        return {"total_count": len(achados), "incomplete_results": False,
                "items": achados[:TETO_BUSCA][(pagina - 1) * n:pagina * n]}


def nomes(candidatos):
    return [c["full_name"] for c in candidatos]


def test_passa_do_teto_da_busca_sem_buraco_nem_repetido():
    estrelas = {f"o/r{i}": 1000 + i for i in range(2500)}
    candidatos = list(candidatos_por_estrelas(BuscaFalsa(estrelas), minimo=1000))
    assert nomes(candidatos) == [f"o/r{i}" for i in range(2499, -1, -1)]


def test_empate_na_fronteira_entre_consultas_nao_perde_ninguem():
    # a 1ª consulta acaba no meio dos 20 empatados com 2000 estrelas
    estrelas = {f"o/topo{i:03d}": 3000 + i for i in range(995)}
    estrelas.update({f"o/empate{i:02d}": 2000 for i in range(20)})
    estrelas.update({f"o/baixo{i:03d}": 1000 + i for i in range(500)})
    api = BuscaFalsa(estrelas)

    candidatos = list(candidatos_por_estrelas(api, minimo=1000))

    assert sorted(nomes(candidatos)) == sorted(estrelas)
    assert len(candidatos) == len(set(nomes(candidatos)))
    valores = [c["stargazers_count"] for c in candidatos]
    assert valores == sorted(valores, reverse=True)
    assert api.consultas[10]["q"].startswith("stars:1000..2000 ")


def test_mais_de_mil_empatados_segue_abaixo_do_empate(caplog):
    estrelas = {f"o/e{i:04d}": 1500 for i in range(1200)}
    estrelas.update({f"o/b{i}": 1200 for i in range(10)})

    with caplog.at_level(logging.WARNING):
        candidatos = list(candidatos_por_estrelas(BuscaFalsa(estrelas), minimo=1000))

    assert len(candidatos) == 1010  # 200 dos empatados ficam sem como aparecer
    assert nomes(candidatos)[-10:] == [f"o/b{i}" for i in range(10)]
    assert "mais de 1000 repositórios com 1500 estrelas" in caplog.text


def test_so_busca_a_pagina_que_o_pipeline_pede():
    api = BuscaFalsa({f"o/r{i}": 1000 + i for i in range(2500)})
    assert len(list(islice(candidatos_por_estrelas(api), 5))) == 5
    assert [c["page"] for c in api.consultas] == [1]


def test_total_da_busca_reaproveita_a_primeira_pagina():
    api = BuscaFalsa({f"o/r{i}": 1000 + i for i in range(1500)})
    assert total_na_busca(api, 1000) == 1500
    next(candidatos_por_estrelas(api, 1000))
    assert api.consultas[0] == api.consultas[1]  # mesma chave de cache


def test_minimo_de_estrelas_e_respeitado():
    api = BuscaFalsa({"o/grande": 5000, "o/pequeno": 999})
    assert nomes(candidatos_por_estrelas(api, minimo=1000)) == ["o/grande"]


def test_usa_actions_descarta_total_count_zero():
    class API:
        def get(self, caminho, params):
            assert caminho == "/repos/o/sem-actions/actions/workflows"
            return {"total_count": 0}

    assert usa_actions(API(), "o/sem-actions") is False


def test_funil_salva_contagens_por_motivo(tmp_path):
    funil = Funil()
    funil.registrar("candidatos da busca", 3, {})
    funil.registrar("com GitHub Actions", 2, {MOTIVO_SEM_ACTIONS: 1})
    funil.registrar("com ≥ 5 releases", 1, {"poucas_releases": 1})
    caminho = tmp_path / "funil.csv"

    funil.salvar(caminho)

    with caminho.open(encoding="utf-8", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    assert list(linhas[0]) == ["ordem", "etapa", "restantes", "descartados", "motivo"]
    assert sum(int(linha["descartados"]) for linha in linhas) == 2
    assert [linha["ordem"] for linha in linhas] == ["1", "2", "3"]

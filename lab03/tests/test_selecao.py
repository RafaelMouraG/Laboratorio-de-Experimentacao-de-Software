import csv
import logging

from lab03.pipeline.selecao import (
    MOTIVO_SEM_ACTIONS,
    Funil,
    buscar_candidatos,
    filtrar_actions,
    usa_actions,
)


class APIFalsa:
    def __init__(self, buscas, workflows=None):
        self.buscas = iter(buscas)
        self.workflows = workflows or {}
        self.consultas = []

    def get(self, caminho, params):
        self.consultas.append((caminho, params))
        if caminho == "/search/repositories":
            try:
                return next(self.buscas)
            except StopIteration:
                return {"total_count": 0, "items": []}
        repo = caminho.removeprefix("/repos/").removesuffix("/actions/workflows")
        return {"total_count": self.workflows[repo]}


def repo(nome, estrelas):
    return {"full_name": nome, "stargazers_count": estrelas}


def test_busca_remove_duplicados_entre_faixas_e_ordena():
    api = APIFalsa(
        [
            {"total_count": 2, "items": [repo("o/a", 2000), repo("o/b", 1500)]},
            {"total_count": 2, "items": [repo("o/a", 2000), repo("o/c", 1200)]},
        ]
    )

    candidatos = buscar_candidatos(api, ["1000..2000", "2000..5000"])

    assert [item["full_name"] for item in candidatos] == ["o/a", "o/b", "o/c"]


def test_busca_avisa_quando_faixa_excede_limite(caplog):
    api = APIFalsa([{"total_count": 1001, "items": [repo("o/a", 2000)]}])

    with caplog.at_level(logging.WARNING):
        buscar_candidatos(api, ["1000..2000"])

    assert "precisa ser quebrada" in caplog.text


def test_usa_actions_descarta_total_count_zero():
    api = APIFalsa([], {"o/sem-actions": 0})

    assert usa_actions(api, "o/sem-actions") is False

    funil = Funil()
    restantes = filtrar_actions(api, [repo("o/sem-actions", 1000)], funil)
    assert restantes == []
    assert funil.linhas[0]["motivo"] == MOTIVO_SEM_ACTIONS
    assert funil.linhas[0]["descartados"] == 1


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

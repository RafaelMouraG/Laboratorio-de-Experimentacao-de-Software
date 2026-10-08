"""Seleção de repositórios candidatos e registro do funil da amostra."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterable

from lab03.pipeline.api import GitHubAPI

log = logging.getLogger(__name__)

CAMINHO_BUSCA = "/search/repositories"
MOTIVO_SEM_ACTIONS = "sem_actions"


def buscar_candidatos(api: GitHubAPI, faixas: Iterable[str]) -> list[dict]:
    """Busca, deduplica e ordena os candidatos por estrelas decrescentes."""
    por_nome: dict[str, dict] = {}
    for faixa in faixas:
        params = {
            "q": f"stars:{faixa} fork:false archived:false",
            "sort": "stars",
            "per_page": 100,
        }
        primeira = api.get(CAMINHO_BUSCA, params)
        total = primeira.get("total_count", 0)
        if total > 1000:
            log.warning(
                "faixa %s retornou %d itens; precisa ser quebrada (limite de 1.000)",
                faixa,
                total,
            )

        itens = list(primeira.get("items", []))
        limite = min(total, 1000)
        pagina = 2
        while len(itens) < limite:
            pagina_resposta = api.get(CAMINHO_BUSCA, {**params, "page": pagina})
            novos = pagina_resposta.get("items", [])
            if not novos:
                break
            itens.extend(novos)
            pagina += 1
        itens = itens[:1000]
        for candidato in itens:
            nome = candidato.get("full_name")
            if nome:
                por_nome[nome] = candidato

    return sorted(
        por_nome.values(),
        key=lambda repo: (-repo.get("stargazers_count", 0), repo["full_name"]),
    )


def usa_actions(api: GitHubAPI, repo: str) -> bool:
    """Retorna se o repositório possui pelo menos um workflow do GitHub Actions."""
    resposta = api.get(f"/repos/{repo}/actions/workflows", {"per_page": 1})
    return resposta.get("total_count", 0) > 0


class Funil:
    """Registra contagens já calculadas pelas etapas do pipeline."""

    CAMPOS = ("ordem", "etapa", "restantes", "descartados", "motivo")

    def __init__(self) -> None:
        self._linhas: list[dict[str, object]] = []

    @property
    def linhas(self) -> list[dict[str, object]]:
        return list(self._linhas)

    def registrar(self, etapa: str, restantes: int, descartados_por_motivo: dict[str, int]) -> None:
        ordem = len(self._linhas) + 1
        if descartados_por_motivo:
            for motivo, descartados in descartados_por_motivo.items():
                self._linhas.append(
                    {
                        "ordem": ordem,
                        "etapa": etapa,
                        "restantes": restantes,
                        "descartados": descartados,
                        "motivo": motivo,
                    }
                )
        else:
            self._linhas.append(
                {
                    "ordem": ordem,
                    "etapa": etapa,
                    "restantes": restantes,
                    "descartados": 0,
                    "motivo": "",
                }
            )

    def salvar(self, caminho_csv: str | Path = "lab03/data/funil.csv") -> None:
        caminho = Path(caminho_csv)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with caminho.open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=self.CAMPOS)
            escritor.writeheader()
            escritor.writerows(self._linhas)


def filtrar_actions(api: GitHubAPI, candidatos: Iterable[dict], funil: Funil) -> list[dict]:
    """Aplica a primeira etapa cara e registra os repositórios sem Actions."""
    restantes = []
    descartados = 0
    for candidato in candidatos:
        repo = candidato["full_name"]
        if usa_actions(api, repo):
            restantes.append(candidato)
        else:
            descartados += 1
    funil.registrar("com GitHub Actions", len(restantes), {MOTIVO_SEM_ACTIONS: descartados})
    return restantes

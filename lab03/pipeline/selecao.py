"""Seleção de repositórios candidatos e registro do funil da amostra."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterator, Optional

from lab03.pipeline.api import GitHubAPI

log = logging.getLogger(__name__)

CAMINHO_BUSCA = "/search/repositories"
TETO_BUSCA = 1000  # o /search não passa disso numa consulta, mesmo paginando
POR_PAGINA = 100
MOTIVO_SEM_ACTIONS = "sem_actions"


def _params(minimo: int, teto: Optional[int], pagina: int) -> dict:
    estrelas = f">={minimo}" if teto is None else f"{minimo}..{teto}"
    return {
        "q": f"stars:{estrelas} fork:false archived:false",
        "sort": "stars",
        "order": "desc",
        "per_page": POR_PAGINA,
        "page": pagina,
    }


def total_na_busca(api: GitHubAPI, minimo: int) -> int:
    """Quantos repositórios a busca acha com `minimo` estrelas ou mais: a 1ª linha do funil.

    É a mesma consulta da 1ª página de `candidatos_por_estrelas`, então sai do cache.
    """
    return api.get(CAMINHO_BUSCA, _params(minimo, None, 1))["total_count"]


def candidatos_por_estrelas(api: GitHubAPI, minimo: int = 1000) -> Iterator[dict]:
    """Repositórios com `minimo` estrelas ou mais, do mais estrelado para baixo, sem pular nenhum.

    Cada consulta do /search para em 1000 itens. Quando uma esgota, a seguinte pede
    `stars:<minimo>..<menor nº de estrelas visto>`; quem estava empatado nesse número volta
    repetido e é pulado pelo nome. Como é um gerador, a página seguinte só é buscada quando o
    pipeline pede mais candidatos.
    """
    vistos: set[str] = set()
    teto: Optional[int] = None
    while teto is None or teto >= minimo:
        lidos, novos, menor = 0, 0, None
        for pagina in range(1, TETO_BUSCA // POR_PAGINA + 1):
            corpo = api.get(CAMINHO_BUSCA, _params(minimo, teto, pagina))
            if corpo.get("incomplete_results"):
                log.warning("busca até %s estrelas, página %d, veio incompleta", teto or "o topo", pagina)
            itens = corpo.get("items", [])
            for item in itens:
                menor = item["stargazers_count"]
                if item["full_name"] not in vistos:
                    vistos.add(item["full_name"])
                    novos += 1
                    yield item
            lidos += len(itens)
            if len(itens) < POR_PAGINA:
                break
        if lidos < TETO_BUSCA or menor is None:
            return  # a consulta acabou antes do teto: não sobrou ninguém
        if novos == 0:
            # mais de 1000 repositórios com o mesmo nº de estrelas: só dá para seguir abaixo dele
            log.warning("mais de %d repositórios com %d estrelas; os que passaram do teto ficam de fora",
                        TETO_BUSCA, menor)
            menor -= 1
        teto = menor


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


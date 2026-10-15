"""Heurística de release corretiva e CFR variante (b), pelo proxy de entrega (RQ 03).

As releases chegam no formato do pipeline (#77): dicts com `tag_name`, `published_at`, `commits`
(cada um com `mensagem`) e `body` (as notas da release, que podem faltar ou vir vazias).

Cada versão da heurística testada contra a amostra-ouro fica em `VERSOES`, para que
`python -m lab03.validacao.avaliar_heuristica` refaça a tabela do artigo. `eh_corretiva` usa a
versão em `VERSAO_ATUAL`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Callable, Iterable, NamedTuple, Optional

from lab03.metricas.frequencia import Data, _data

PRAZO = timedelta(days=7)

# `v2.3.1`, `2.3.1`, `release-2.3.1`, `pacote@2.3.1`, `rust-v0.0.17`, `curl-8_17_0`. O que vem antes
# do número é o pacote, para um monorepo não comparar a versão de um pacote com a de outro.
_VERSAO = re.compile(r"(?:^|[@/_-])v?(\d+)[._](\d+)(?:[._](\d+))?(?!\d)", re.IGNORECASE)
_SEPARADORES = "@/_- "

# Commits: `fix`, `fixes`, `fixed`, `fix(escopo):`, `hotfix`, `revert`, `Revert "..."`.
_COMMIT_CORRECAO = re.compile(r"\b(?:hot)?fix|\brevert", re.IGNORECASE)
# Notas: menções a correção contra menções a novidade.
_NOTAS_CORRECAO = re.compile(r"\b(?:fix|bug)", re.IGNORECASE)
_NOTAS_NOVIDADE = re.compile(r"\b(?:feat|features?|add(?:s|ed)?|new|introduc\w*|support)\b", re.IGNORECASE)


class Versao(NamedTuple):
    pacote: str
    numeros: tuple[int, int, int]  # major, minor, patch; `v1.89` vira (1, 89, 0)


def versao(tag: str) -> Optional[Versao]:
    """Versão da tag, ou None se ela não tem um `X.Y` ou `X.Y.Z`."""
    achado = _VERSAO.search(tag)
    if achado is None:
        return None
    pacote = tag[:achado.start()].rstrip(_SEPARADORES)
    if pacote.lower() == "release":  # `release-2.3.1` é o mesmo pacote que `v2.3.0`
        pacote = ""
    major, minor, patch = achado.groups()
    return Versao(pacote.lower(), (int(major), int(minor), int(patch or 0)))


def so_patch(release: dict, anterior: Optional[dict]) -> Optional[bool]:
    """A versão só subiu no patch em relação à anterior (`2.3.0 → 2.3.1`).

    None quando não dá para comparar: tag que não é semver, sem anterior ou pacotes diferentes.
    """
    if anterior is None:
        return None
    nova, velha = versao(release["tag_name"]), versao(anterior["tag_name"])
    if nova is None or velha is None or nova.pacote != velha.pacote:
        return None
    return nova.numeros[:2] == velha.numeros[:2] and nova.numeros[2] > velha.numeros[2]


def e_patch(release: dict) -> Optional[bool]:
    """O patch da própria versão é maior que zero; None se a tag não é semver."""
    nova = versao(release["tag_name"])
    return None if nova is None else nova.numeros[2] > 0


def commit_de_correcao(release: dict) -> bool:
    return any(_COMMIT_CORRECAO.search(c.get("mensagem") or "") for c in release.get("commits") or [])


def notas_de_correcao(release: dict) -> bool:
    """As notas falam de correção pelo menos tanto quanto de novidade. Sem notas, dá True."""
    notas = release.get("body") or ""
    return len(_NOTAS_CORRECAO.findall(notas)) >= len(_NOTAS_NOVIDADE.findall(notas))


def _v1(release: dict, anterior: Optional[dict]) -> bool:
    return bool(so_patch(release, anterior)) or commit_de_correcao(release)


def _v2(release: dict, anterior: Optional[dict]) -> bool:
    patch = so_patch(release, anterior)
    return commit_de_correcao(release) if patch is None else patch and commit_de_correcao(release)


def _v3(release: dict, anterior: Optional[dict]) -> bool:
    patch = e_patch(release)
    return commit_de_correcao(release) if patch is None else patch


def _v4(release: dict, anterior: Optional[dict]) -> bool:
    return _v3(release, anterior) and notas_de_correcao(release)


class VersaoHeuristica(NamedTuple):
    regra: str
    decidir: Callable[[dict, Optional[dict]], bool]


VERSOES = {
    "v1": VersaoHeuristica(
        "só o patch subiu em relação à anterior **ou** algum commit com `fix`, `hotfix` ou `revert`",
        _v1),
    "v2": VersaoHeuristica(
        "só o patch subiu em relação à anterior **e** algum commit com `fix`, `hotfix` ou `revert`",
        _v2),
    "v3": VersaoHeuristica(
        "o patch da própria versão é maior que zero (`x.y.z`, `z > 0`), sem olhar a anterior",
        _v3),
    "v4": VersaoHeuristica(
        "v3 **e** as notas da release citam correção (`fix`, `bug`) pelo menos tantas vezes quanto "
        "novidade (`feat`, `feature`, `add`, `new`, `introduce`, `support`)",
        _v4),
}
VERSAO_ATUAL = "v4"


def eh_corretiva(release: dict, anterior: Optional[dict] = None) -> bool:
    """Se `release` existe para corrigir um defeito, pela versão atual da heurística.

    Nas versões que comparam com a anterior (v1, v2), uma tag que não é semver fica só com a regra
    das mensagens de commit. A partir da v3 a anterior não entra: num repositório com várias linhas
    de versão, a anterior pela data costuma ser de outra linha (`v9.2.8 → v8.19.14`).
    """
    return VERSOES[VERSAO_ATUAL].decidir(release, anterior)


@dataclass(frozen=True)
class CFREntrega:
    taxa: Optional[float]  # falharam / avaliadas; None sem nenhuma avaliada
    avaliadas: int
    falharam: int
    censuradas: int  # publicadas nos últimos 7 dias da janela


def cfr_entrega(releases: Iterable[dict], fim: Data) -> CFREntrega:
    """A release R falhou se a próxima sai em até 7 dias e é corretiva.

    Só a release seguinte conta. As publicadas a menos de 7 dias do fim da janela (inclusivo) ficam
    fora do denominador, porque ainda não dá para saber se vão ganhar correção.
    """
    ordenadas = sorted(releases, key=lambda r: _data(r["published_at"]))
    limite = _data(fim, fim=True)
    avaliadas = falharam = censuradas = 0
    for i, release in enumerate(ordenadas):
        publicada = _data(release["published_at"])
        if publicada + PRAZO > limite:
            censuradas += 1
            continue
        avaliadas += 1
        proxima = ordenadas[i + 1] if i + 1 < len(ordenadas) else None
        if (proxima is not None and _data(proxima["published_at"]) - publicada <= PRAZO
                and eh_corretiva(proxima, release)):
            falharam += 1
    return CFREntrega(falharam / avaliadas if avaliadas else None, avaliadas, falharam, censuradas)

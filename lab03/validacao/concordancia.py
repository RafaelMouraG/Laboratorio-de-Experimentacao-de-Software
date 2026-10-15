"""Calcula a concordância e monta o consenso da amostra-ouro.

Execute da raiz do repositório com ``python -m lab03.validacao.concordancia``.
As planilhas precisam estar completas antes que o cálculo seja feito.
"""

from __future__ import annotations

import csv
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable, Sequence

from statsmodels.stats.inter_rater import aggregate_raters, fleiss_kappa

AVALIADORES = ("mateusdsoc", "RafaelMouraG", "Athoosz")
DIMENSOES_REPOS = {
    "tipo_projeto": frozenset(("biblioteca", "aplicacao", "cli", "outro")),
    "entregas_reais": frozenset(("sim", "nao", "incerto")),
}
DIMENSOES_RELEASES = {"corretiva": frozenset(("sim", "nao"))}

_CAMPOS_REPOS = ("repo", "url", "tipo_projeto", "entregas_reais", "observacao")
_CAMPOS_RELEASES = ("repo", "tag_name", "url_release", "url_compare", "corretiva", "observacao")
_CAMPOS_EMPATES = (
    "tipo",
    "item",
    "dimensao",
    "rotulo_mateusdsoc",
    "rotulo_RafaelMouraG",
    "rotulo_Athoosz",
    "decisao",
    "justificativa",
)


class ErroRotulagem(ValueError):
    """Indica que as planilhas não podem ser usadas no cálculo."""


def faixa_landis_koch(kappa: float) -> str:
    """Retorna a interpretação usual de Landis & Koch."""
    if math.isnan(kappa):
        return "indefinida"
    if kappa < 0:
        return "pobre"
    if kappa <= 0.20:
        return "leve"
    if kappa <= 0.40:
        return "razoavel"
    if kappa <= 0.60:
        return "moderada"
    if kappa <= 0.80:
        return "substancial"
    return "quase perfeita"


def concordancia_dimensao(rotulos: Sequence[Sequence[str]]) -> tuple[float, float]:
    """Retorna ``(kappa, percentual)`` para itens x avaliadores."""
    if not rotulos:
        raise ValueError("não há itens para calcular a concordância")
    if any(len(item) < 2 for item in rotulos):
        raise ValueError("cada item precisa ter pelo menos dois rótulos")
    tabela, _ = aggregate_raters(rotulos)
    kappa = float(fleiss_kappa(tabela))
    percentual = 100 * sum(len(set(item)) == 1 for item in rotulos) / len(rotulos)
    return kappa, percentual


def consenso(rotulos: Sequence[str]) -> str | None:
    """Retorna a maioria simples; ``None`` representa empate 1-1-1."""
    contagem = Counter(rotulos)
    mais_votado = contagem.most_common()
    if len(mais_votado) == 1 or mais_votado[0][1] >= 2:
        return mais_votado[0][0]
    return None


def _ler(caminho: Path, campos: Sequence[str]) -> list[dict[str, str]]:
    if not caminho.is_file():
        raise ErroRotulagem(f"planilha ausente: {caminho}")
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        faltantes = [campo for campo in campos if campo not in (leitor.fieldnames or [])]
        if faltantes:
            raise ErroRotulagem(f"{caminho}: colunas ausentes: {', '.join(faltantes)}")
        linhas = list(leitor)
    if not linhas:
        raise ErroRotulagem(f"{caminho}: planilha sem linhas")
    return [{campo: (linha.get(campo) or "").strip() for campo in campos} for linha in linhas]


def _validar(
    planilhas: dict[str, list[dict[str, str]]],
    tipo: str,
    dimensoes: dict[str, frozenset[str]],
) -> list[tuple[str, ...]]:
    chaves = []
    for avaliador, linhas in planilhas.items():
        chave_linha = (
            (linha["repo"],) if tipo == "repos" else (linha["repo"], linha["tag_name"])
            for linha in linhas
        )
        chaves_avaliador = list(chave_linha)
        if len(set(chaves_avaliador)) != len(chaves_avaliador):
            raise ErroRotulagem(f"{avaliador}_{tipo}.csv: há itens duplicados")
        chaves.append(chaves_avaliador)
        for numero, linha in enumerate(linhas, 2):
            for dimensao, valores in dimensoes.items():
                valor = linha[dimensao]
                if not valor:
                    raise ErroRotulagem(
                        f"{avaliador}_{tipo}.csv, linha {numero}: rótulo ausente em {dimensao}"
                    )
                if valor not in valores:
                    permitidos = ", ".join(sorted(valores))
                    raise ErroRotulagem(
                        f"{avaliador}_{tipo}.csv, linha {numero}: valor inválido "
                        f"em {dimensao}: {valor!r}; permitidos: {permitidos}"
                    )
    if any(chave != chaves[0] for chave in chaves[1:]):
        raise ErroRotulagem(f"as planilhas de {tipo} não contêm os mesmos itens ou estão em ordem diferente")
    return chaves[0]


def _carregar_planilhas(pasta: Path, tipo: str, dimensoes: dict[str, frozenset[str]]):
    campos = _CAMPOS_REPOS if tipo == "repos" else _CAMPOS_RELEASES
    planilhas = {
        avaliador: _ler(pasta / "rotulos" / f"{avaliador}_{tipo}.csv", campos)
        for avaliador in AVALIADORES
    }
    chaves = _validar(planilhas, tipo, dimensoes)
    return planilhas, chaves


def _ler_decisoes(caminho: Path) -> dict[tuple[str, str], tuple[str, str]]:
    if not caminho.exists():
        return {}
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        faltantes = [campo for campo in _CAMPOS_EMPATES if campo not in (leitor.fieldnames or [])]
        if faltantes:
            raise ErroRotulagem(f"{caminho}: colunas ausentes: {', '.join(faltantes)}")
        linhas = [
            {campo: (linha.get(campo) or "").strip() for campo in _CAMPOS_EMPATES}
            for linha in leitor
        ]
    decisoes = {}
    for numero, linha in enumerate(linhas, 2):
        chave = (linha["dimensao"], linha["item"])
        if linha["decisao"]:
            permitidos = DIMENSOES_REPOS.get(linha["dimensao"], DIMENSOES_RELEASES.get(linha["dimensao"]))
            if permitidos is None or linha["decisao"] not in permitidos:
                raise ErroRotulagem(
                    f"{caminho}, linha {numero}: decisão inválida em {linha['dimensao']}: "
                    f"{linha['decisao']!r}"
                )
            decisoes[chave] = (linha["decisao"], linha["justificativa"])
        elif linha["justificativa"]:
            raise ErroRotulagem(f"{caminho}, linha {numero}: justificativa sem decisão")
    return decisoes


def _escrever(caminho: Path, campos: Sequence[str], linhas: Iterable[dict[str, str]]) -> None:
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(linhas)


def _processar_tipo(
    pasta: Path,
    tipo: str,
    dimensoes: dict[str, frozenset[str]],
    caminho_empates: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    planilhas, chaves = _carregar_planilhas(pasta, tipo, dimensoes)
    consenso_linhas = []
    empates = []
    decisoes = _ler_decisoes(caminho_empates)
    for indice, chave in enumerate(chaves):
        linha = {"repo": chave[0]}
        if tipo == "releases":
            linha["tag_name"] = chave[1]
        for dimensao in dimensoes:
            rotulos = [planilhas[avaliador][indice][dimensao] for avaliador in AVALIADORES]
            valor = consenso(rotulos)
            if valor is None:
                item = "|".join(chave)
                decisao, justificativa = decisoes.get((dimensao, item), ("", ""))
                empates.append({
                    "tipo": tipo,
                    "item": item,
                    "dimensao": dimensao,
                    **{f"rotulo_{avaliador}": rotulo for avaliador, rotulo in zip(AVALIADORES, rotulos)},
                    "decisao": decisao,
                    "justificativa": justificativa,
                })
                valor = decisao
            linha[f"consenso_{dimensao}"] = valor
        consenso_linhas.append(linha)
    return consenso_linhas, empates


def executar(pasta: Path) -> None:
    """Valida planilhas e grava concordância, empates e consensos."""
    repos, _ = _carregar_planilhas(pasta, "repos", DIMENSOES_REPOS)
    releases, _ = _carregar_planilhas(pasta, "releases", DIMENSOES_RELEASES)
    resultados = []
    for tipo, planilhas, dimensoes in (
        ("repos", repos, DIMENSOES_REPOS),
        ("releases", releases, DIMENSOES_RELEASES),
    ):
        quantidade = len(next(iter(planilhas.values())))
        for dimensao in dimensoes:
            rotulos = [
                [planilhas[avaliador][indice][dimensao] for avaliador in AVALIADORES]
                for indice in range(quantidade)
            ]
            kappa, percentual = concordancia_dimensao(rotulos)
            resultados.append({
                "dimensao": dimensao,
                "itens": str(quantidade),
                "kappa": f"{kappa:.6f}",
                "faixa_landis_koch": faixa_landis_koch(kappa),
                "concordancia_percentual": f"{percentual:.2f}",
            })
    caminho_empates = pasta / "empates.csv"
    consenso_repos, empates_repos = _processar_tipo(pasta, "repos", DIMENSOES_REPOS, caminho_empates)
    consenso_releases, empates_releases = _processar_tipo(
        pasta, "releases", DIMENSOES_RELEASES, caminho_empates
    )
    _escrever(pasta / "concordancia.csv",
              ("dimensao", "itens", "kappa", "faixa_landis_koch", "concordancia_percentual"),
              resultados)
    _escrever(caminho_empates, _CAMPOS_EMPATES, empates_repos + empates_releases)
    _escrever(pasta / "consenso_repos.csv", ("repo", "consenso_tipo_projeto", "consenso_entregas_reais"),
              consenso_repos)
    _escrever(pasta / "consenso_releases.csv", ("repo", "tag_name", "consenso_corretiva"),
              consenso_releases)


def main() -> int:
    pasta = Path(__file__).resolve().parent
    try:
        executar(pasta)
    except (ErroRotulagem, ValueError) as erro:
        print(f"Erro nas rotulagens: {erro}", file=sys.stderr)
        return 1
    print(f"Concordância e consenso gravados em {pasta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

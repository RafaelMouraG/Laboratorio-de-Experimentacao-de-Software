"""Precisão, recall e F1 de cada versão da heurística de release corretiva (#96).

`python -m lab03.validacao.avaliar_heuristica`, da raiz do repositório, depois que a #97 gravou
`consenso_releases.csv`. Roda todas as versões de `corretiva.VERSOES` nas releases de
`heuristica_entrada.jsonl.gz` e regrava `heuristica_versoes.md` com uma linha por versão.
"""

from __future__ import annotations

import csv
import gzip
import json
import sys
from pathlib import Path

from sklearn.metrics import precision_recall_fscore_support

from lab03.metricas.corretiva import VERSAO_ATUAL, VERSOES

PASTA = Path(__file__).resolve().parent
ENTRADA = "heuristica_entrada.jsonl.gz"
CONSENSO = "consenso_releases.csv"
SAIDA = "heuristica_versoes.md"
F1_MINIMO = 0.70


class ErroAvaliacao(ValueError):
    """Faltam arquivos ou rótulos para avaliar a heurística."""


def ler_entrada(caminho: Path) -> list[dict]:
    """Cada linha no formato do pipeline: as notas viram `body`, como em `releases.CAMPOS_RELEASE`."""
    with gzip.open(caminho, "rt", encoding="utf-8") as arquivo:
        linhas = [json.loads(linha) for linha in arquivo if linha.strip()]
    return [{**linha, "body": linha.get("notas") or ""} for linha in linhas]


def ler_consenso(caminho: Path) -> dict[tuple[str, str], bool]:
    if not caminho.is_file():
        raise ErroAvaliacao(f"{caminho} não existe; rode antes python -m lab03.validacao.concordancia")
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    consenso = {}
    for numero, linha in enumerate(linhas, 2):
        valor = (linha.get("consenso_corretiva") or "").strip()
        if valor not in {"sim", "nao"}:
            raise ErroAvaliacao(f"{caminho}, linha {numero}: consenso_corretiva {valor!r} (empate sem decisão?)")
        consenso[(linha["repo"], linha["tag_name"])] = valor == "sim"
    return consenso


def avaliar(releases: list[dict], consenso: dict[tuple[str, str], bool]) -> list[dict]:
    """Uma linha por versão, com precisão, recall, F1 e quantas releases ela marcou."""
    faltando = [r for r in releases if (r["repo"], r["tag_name"]) not in consenso]
    if faltando:
        raise ErroAvaliacao(f"{len(faltando)} releases da entrada sem consenso, ex.: "
                            f"{faltando[0]['repo']} {faltando[0]['tag_name']}")
    esperado = [consenso[(r["repo"], r["tag_name"])] for r in releases]
    resultados = []
    for nome, versao in VERSOES.items():
        previsto = [versao.decidir(r, r.get("anterior")) for r in releases]
        precisao, recall, f1, _ = precision_recall_fscore_support(
            esperado, previsto, average="binary", pos_label=True, zero_division=0
        )
        resultados.append({"versao": nome, "regra": versao.regra, "precisao": precisao,
                           "recall": recall, "f1": f1, "marcadas": sum(previsto)})
    return resultados


def tabela_markdown(resultados: list[dict], total: int, corretivas: int) -> str:
    linhas = [
        "# Versões da heurística de release corretiva",
        "",
        "Gerado por `python -m lab03.validacao.avaliar_heuristica`. Cada versão roda nas "
        f"{total} releases da amostra-ouro e é comparada com o consenso dos três avaliadores "
        f"({corretivas} corretivas). A versão usada na CFR (b) é a **{VERSAO_ATUAL}**.",
        "",
        "| Versão | Regra | Precisão | Recall | F1 | Marcadas |",
        "|---|---|---|---|---|---|",
    ]
    for r in resultados:
        linhas.append(f"| {r['versao']} | {r['regra']} | {r['precisao']:.3f} | {r['recall']:.3f} "
                      f"| {r['f1']:.3f} | {r['marcadas']} |")
    return "\n".join(linhas) + "\n"


def executar(pasta: Path = PASTA) -> list[dict]:
    releases = ler_entrada(pasta / ENTRADA)
    consenso = ler_consenso(pasta / CONSENSO)
    resultados = avaliar(releases, consenso)
    corretivas = sum(consenso[(r["repo"], r["tag_name"])] for r in releases)
    (pasta / SAIDA).write_text(tabela_markdown(resultados, len(releases), corretivas), encoding="utf-8")
    return resultados


def main() -> int:
    try:
        resultados = executar()
    except ErroAvaliacao as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    for r in resultados:
        print(f"{r['versao']}: precisão {r['precisao']:.3f}, recall {r['recall']:.3f}, F1 {r['f1']:.3f}")
    atual = next(r for r in resultados if r["versao"] == VERSAO_ATUAL)
    if atual["f1"] < F1_MINIMO:
        print(f"Atenção: F1 da {VERSAO_ATUAL} abaixo de {F1_MINIMO}", file=sys.stderr)
    print(f"Tabela gravada em {PASTA / SAIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

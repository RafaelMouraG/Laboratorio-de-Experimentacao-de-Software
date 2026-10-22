"""Sorteio dos commits para medir a precisão da detecção de agentes (#120).

`python -m lab03.validacao.sortear_ia`, da raiz do repositório.

1. Os commits de `lab03/data/commits_ia.csv` viram um por linha: o mesmo commit aparece uma vez por
   rastro (ex.: trailer do Claude e branch `claude/`), e a precisão é por commit.
2. 100 deles com `sample(n=100, random_state=42)`.
3. `amostra_ia.csv` guarda o sorteio com as ferramentas e famílias detectadas. As planilhas de cada
   avaliador só têm o link: quem confere não vê o que a detecção achou, para não ser puxado por ela.
   Planilha que já existe não é sobrescrita.

Não chama a API.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from lab03.validacao.sortear import AVALIADORES, SEMENTE, _escrever_csv

N_COMMITS = 100
PASTA = Path("lab03/validacao")
COMMITS_IA = Path("lab03/data/commits_ia.csv")

CAMPOS_AMOSTRA = ("repo", "sha", "data", "url", "ferramentas", "familias")
CAMPOS_ROTULO = ("repo", "sha", "url", "com_agente", "observacao")


def url_commit(repo: str, sha: str) -> str:
    return f"https://github.com/{repo}/commit/{sha}"


def um_por_commit(rastros: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por (repo, sha), com as ferramentas e famílias de todos os rastros juntas."""
    juntar = lambda valores: ";".join(sorted(set(valores)))  # noqa: E731
    return (
        rastros.groupby(["repo", "sha"], as_index=False)
        .agg(data=("data", "min"), ferramentas=("ferramenta", juntar), familias=("familia", juntar))
        .sort_values(["repo", "sha"], ignore_index=True)
    )


def sortear(commits: pd.DataFrame, n: int = N_COMMITS, semente: int = SEMENTE) -> pd.DataFrame:
    """`n` commits sorteados. A ordem do `um_por_commit` é fixa, então o sorteio também é; a ordem
    final por repo e data é só para a planilha ficar fácil de percorrer."""
    amostra = commits.sample(n=min(n, len(commits)), random_state=semente)
    amostra = amostra.assign(url=[url_commit(r, s) for r, s in zip(amostra["repo"], amostra["sha"])])
    return amostra.sort_values(["repo", "data"], ignore_index=True)


def gravar(pasta: Path, amostra: pd.DataFrame, avaliadores: Iterable[str] = AVALIADORES) -> list[Path]:
    """Grava a amostra e as planilhas. Devolve as planilhas que já existiam e foram mantidas."""
    linhas = amostra.to_dict("records")
    _escrever_csv(pasta / "amostra_ia.csv", CAMPOS_AMOSTRA, linhas)
    mantidas = []
    for login in avaliadores:
        planilha = pasta / "rotulos" / f"{login}_ia.csv"
        if planilha.exists():
            mantidas.append(planilha)
            continue
        _escrever_csv(planilha, CAMPOS_ROTULO, linhas)
    return mantidas


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lab03.validacao.sortear_ia", description=__doc__.split("\n")[0])
    parser.add_argument("--commits", default=str(COMMITS_IA))
    args = parser.parse_args(argv)

    commits = um_por_commit(pd.read_csv(args.commits))
    amostra = sortear(commits)
    mantidas = gravar(PASTA, amostra)
    print(f"{len(amostra)} de {len(commits)} commits com rastro em {PASTA / 'amostra_ia.csv'}")
    for planilha in mantidas:
        print(f"{planilha} já existia e foi mantida; apague para gerar de novo", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

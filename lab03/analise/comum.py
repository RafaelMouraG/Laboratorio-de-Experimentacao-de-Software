"""Carregamento e gravação compartilhados pelas análises (#108)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "data"
SAIDA = RAIZ / "analise" / "saida"
FIGURAS = RAIZ / "relatorio" / "figuras"


def carregar(dados: Path = DADOS) -> pd.DataFrame:
    """Junta ``repos.csv`` e ``metricas.csv``, uma linha por repositório."""
    repos = pd.read_csv(dados / "repos.csv")
    metricas = pd.read_csv(dados / "metricas.csv")
    return repos.merge(metricas, on="repo", how="left", validate="one_to_one")


def salvar_tabela(df: pd.DataFrame, nome: str, pasta: Path = SAIDA) -> None:
    """Grava ``nome.csv`` e ``nome.tex`` em ``lab03/analise/saida``."""
    pasta.mkdir(parents=True, exist_ok=True)
    df.to_csv(pasta / f"{nome}.csv", index=False)
    df.to_latex(pasta / f"{nome}.tex", index=False, float_format="%.3f")


def salvar_figura(fig, nome: str, pasta: Path = FIGURAS) -> None:
    """Grava a figura em PDF em ``lab03/relatorio/figuras``."""
    pasta.mkdir(parents=True, exist_ok=True)
    fig.savefig(pasta / f"{nome}.pdf", bbox_inches="tight")

"""Parâmetros da simulação tirados de `data/prs.csv`, em escala log.

Cada grupo vira uma lognormal: `mu` é a média do log das horas (o log da mediana) e `sigma` é o
desvio padrão desse log. O Shapiro-Wilk no log diz se a lognormal serve ou se os dados pedem outra
distribuição.

`python -m lab04.simulacao.parametros` recalcula e reescreve a tabela do `cenario.md`.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

LAB = Path(__file__).resolve().parents[1]
CSV = LAB / "data" / "prs.csv"
CENARIO = LAB / "cenario.md"
INICIO = "<!-- parametros:inicio -->"
FIM = "<!-- parametros:fim -->"


@dataclass(frozen=True)
class Parametros:
    grupo: str
    n: int
    mediana_horas: float
    mu: float
    sigma: float
    shapiro_p: float

    @property
    def mediana_lognormal(self) -> float:
        return math.exp(self.mu)


def calcular(csv: Path = CSV) -> dict[str, Parametros]:
    prs = pd.read_csv(csv)
    horas = prs["horas_ate_merge"].astype(float)
    if (horas <= 0).any():
        raise ValueError("horas_ate_merge precisa ser positivo para entrar no log")
    resultado = {}
    for grupo, h in horas.groupby(prs["grupo"]):
        log = np.log(h.to_numpy())
        resultado[grupo] = Parametros(
            grupo=str(grupo),
            n=len(log),
            mediana_horas=float(np.median(h)),
            mu=float(log.mean()),
            sigma=float(log.std(ddof=1)),
            shapiro_p=float(stats.shapiro(log).pvalue),
        )
    return resultado


def sigma_comum(parametros: dict[str, Parametros]) -> float:
    """σ do cenário base: média dos σ dos grupos, para efeito zero ser H₀ dos dois testes."""
    return float(np.mean([p.sigma for p in parametros.values()]))


def tabela(parametros: dict[str, Parametros]) -> str:
    linhas = [
        "| Grupo | n | Mediana real (h) | μ = média do log | σ = desvio do log | exp(μ) (h) | Shapiro no log (p) |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in parametros.values():
        linhas.append(
            f"| {p.grupo} | {p.n} | {p.mediana_horas:.1f} | {p.mu:.3f} | {p.sigma:.3f} "
            f"| {p.mediana_lognormal:.1f} | {p.shapiro_p:.3f} |"
        )
    linhas += ["", f"σ comum do cenário base: {sigma_comum(parametros):.3f}"]
    return "\n".join(linhas)


def reescrever(cenario: Path, conteudo: str) -> None:
    texto = cenario.read_text(encoding="utf-8")
    antes, resto = texto.split(INICIO, 1)
    _, depois = resto.split(FIM, 1)
    cenario.write_text(f"{antes}{INICIO}\n{conteudo}\n{FIM}{depois}", encoding="utf-8")


def main() -> int:
    if not CSV.exists():
        print(f"{CSV} ainda não existe (coleta da #143)", file=sys.stderr)
        return 1
    conteudo = tabela(calcular())
    reescrever(CENARIO, conteudo)
    print(conteudo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

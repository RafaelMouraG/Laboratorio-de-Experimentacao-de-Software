"""Um conjunto simulado com efeito conhecido, passado pelos dois testes.

O efeito é a diferença entre os μ dos grupos reais, então o conjunto imita o tamanho de efeito que
os dados sugerem, com H₁ verdadeira por construção.

`python -m lab04.simulacao.exemplo` recalcula e reescreve a tabela do `README.md`.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from lab04.simulacao import parametros
from lab04.simulacao.gerador import cenario_base, efeito_observado, gerar
from lab04.simulacao.testes import delta_cliff, g_hedges, mann_whitney, welch

SEMENTE = 42
README = parametros.LAB / "README.md"
INICIO = "<!-- exemplo:inicio -->"
FIM = "<!-- exemplo:fim -->"


def rodar(csv: Path = parametros.CSV) -> dict:
    p = parametros.calcular(csv)
    cenario = cenario_base(p)
    efeito = efeito_observado(p)
    com, sem = gerar(np.random.default_rng(SEMENTE), cenario.n, cenario.mu, cenario.sigma, efeito)
    return {
        "cenario": cenario,
        "efeito": efeito,
        "mediana_com": float(np.median(com)),
        "mediana_sem": float(np.median(sem)),
        "media_com": float(com.mean()),
        "media_sem": float(sem.mean()),
        "welch": welch(com, sem),
        "mann_whitney": mann_whitney(com, sem),
        "g": float(g_hedges(com, sem)[0]),
        "delta": float(delta_cliff(com, sem)[0]),
    }


def tabela(r: dict) -> str:
    c = r["cenario"]
    w, m = r["welch"], r["mann_whitney"]
    return "\n".join([
        f"Semente {SEMENTE}, n = {c.n[0]} por grupo, σ = {c.sigma[0]:.3f}, μ sem bot = {c.mu:.3f} "
        f"e efeito = {r['efeito']:.3f} no log (tempos do grupo com bot × {math.exp(r['efeito']):.2f}).",
        "",
        "| Grupo simulado | Mediana (h) | Média (h) |",
        "|---|---|---|",
        f"| com_bot | {r['mediana_com']:.1f} | {r['media_com']:.1f} |",
        f"| sem_bot | {r['mediana_sem']:.1f} | {r['media_sem']:.1f} |",
        "",
        "| Teste | Estatística | p-valor | Tamanho de efeito |",
        "|---|---|---|---|",
        f"| t de Welch | t = {w.estatistica[0]:.3f} | {w.p[0]:.4f} | g de Hedges = {r['g']:.3f} |",
        f"| Mann-Whitney | U = {m.estatistica[0]:.0f} | {m.p[0]:.4f} | δ de Cliff = {r['delta']:.3f} |",
    ])


def main() -> int:
    conteudo = tabela(rodar())
    parametros.reescrever(README, conteudo, INICIO, FIM)
    print(conteudo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

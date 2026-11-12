"""[Extra] p-valor × tamanho do efeito com amostra grande.

Cenário base com a mediana do grupo com bot só 10% maior, cerca de meia hora num PR que leva horas,
e n de 30 a 30.000 por grupo. O p-valor cai com o n; o tamanho do efeito e a diferença em horas,
não.

Os 2% sugeridos na issue não servem aqui: com σ = 2,1 no log, um deslocamento de 2% fica abaixo do
ruído mesmo com 30.000 PRs por grupo (p ≈ 0,7 no Mann-Whitney), e a tabela não mostraria nada. Com
10%, o efeito é desprezível na prática e, mesmo assim, o p-valor despenca dentro da grade.

Cada n sorteia 200 conjuntos, e a tabela mostra a mediana de cada medida. Com um conjunto só, o
p-valor e o δ dos n pequenos variam tanto de uma semente para outra que a tendência some.

`python -m lab04.simulacao.amostra_grande` grava `saida/amostra_grande.csv` e reescreve a tabela do
`README.md`. O dashboard só lê o CSV.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from lab04.simulacao import motor, parametros
from lab04.simulacao.gerador import Cenario, cenario_base, gerar
from lab04.simulacao.testes import delta_cliff, g_hedges, mann_whitney, welch

AUMENTO = 0.10
EFEITO = math.log(1 + AUMENTO)
TAMANHOS = (30, 300, 3_000, 30_000)
N_REP = 200
ALFA = 0.05
PREFIXO = "amostra_grande_n"
SAIDA = parametros.LAB / "saida" / "amostra_grande.csv"
COLUNAS = [
    "n", "n_rep", "p_welch", "p_mann_whitney", "rejeicao_welch", "rejeicao_mann_whitney",
    "g_hedges", "delta_cliff", "diferenca_medianas_h",
]
README = parametros.LAB / "README.md"
INICIO = "<!-- amostra_grande:inicio -->"
FIM = "<!-- amostra_grande:fim -->"


def delta_verdadeiro(c: Cenario, efeito: float = EFEITO) -> float:
    """δ de Cliff da população: com o mesmo σ, P(X > Y) = Φ(efeito / (σ√2))."""
    return 2 * stats.norm.cdf(efeito / (c.sigma[0] * math.sqrt(2))) - 1


def diferenca_verdadeira_h(c: Cenario, efeito: float = EFEITO) -> float:
    """Diferença entre as medianas da população, em horas: exp(μ) · (exp(efeito) − 1)."""
    return math.exp(c.mu) * math.expm1(efeito)


def medir(c: Cenario, n: int, n_rep: int = N_REP, semente: int = motor.SEMENTE) -> dict[str, float]:
    """Mediana de cada medida em `n_rep` conjuntos com `n` PRs por grupo."""
    rng = motor.gerador(f"{PREFIXO}{n}", EFEITO, semente)
    com, sem = gerar(rng, n, c.mu, c.sigma, EFEITO, repeticoes=n_rep)
    p_w, p_m = welch(com, sem).p, mann_whitney(com, sem).p
    return {
        "n": n,
        "n_rep": n_rep,
        "p_welch": float(np.median(p_w)),
        "p_mann_whitney": float(np.median(p_m)),
        "rejeicao_welch": float(np.mean(p_w < ALFA)),
        "rejeicao_mann_whitney": float(np.mean(p_m < ALFA)),
        "g_hedges": float(np.median(g_hedges(com, sem))),
        "delta_cliff": float(np.median(delta_cliff(com, sem))),
        "diferenca_medianas_h": float(np.median(np.median(com, axis=1) - np.median(sem, axis=1))),
    }


def rodar(csv: Path = parametros.CSV) -> pd.DataFrame:
    c = cenario_base(parametros.calcular(csv))
    return pd.DataFrame([medir(c, n) for n in TAMANHOS], columns=COLUNAS)


def ler(caminho: Path = SAIDA) -> pd.DataFrame:
    r = pd.read_csv(caminho, float_precision="round_trip")
    faltam = set(TAMANHOS) - set(r["n"])
    if faltam:
        raise ValueError(f"faltam os n {sorted(faltam)} no amostra_grande.csv; rode o amostra_grande")
    return r.sort_values("n", ignore_index=True)


def p_valor(p: float) -> str:
    """Notação científica abaixo de 0,001, que é onde os p-valores da grade grande caem."""
    if p >= 0.001:
        return f"{p:.3f}"
    mantissa, expoente = f"{p:.1e}".split("e")
    return f"{mantissa} × 10^{int(expoente)}"


def tabela(r: pd.DataFrame, csv: Path = parametros.CSV) -> str:
    c = cenario_base(parametros.calcular(csv))
    linhas = [
        f"Cenário base com a mediana do grupo com bot ×{1 + AUMENTO:.2f} ({diferenca_verdadeira_h(c) * 60:.0f} min "
        f"a mais sobre a mediana de {math.exp(c.mu):.1f} h do grupo sem bot; δ de Cliff da população = "
        f"{delta_verdadeiro(c):.3f}). Mediana de {int(r['n_rep'].iloc[0])} conjuntos por n, semente {motor.SEMENTE}.",
        "",
        "| n por grupo | p-valor, Welch | p-valor, Mann-Whitney | Rejeita a 5%, Welch | Rejeita a 5%, Mann-Whitney | g de Hedges | δ de Cliff | Diferença de medianas |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for _, l in r.iterrows():
        linhas.append(
            f"| {int(l.n)} | {p_valor(l.p_welch)} | {p_valor(l.p_mann_whitney)} | {l.rejeicao_welch:.0%} "
            f"| {l.rejeicao_mann_whitney:.0%} | {l.g_hedges:.3f} | {l.delta_cliff:.3f} "
            f"| {l.diferenca_medianas_h * 60:.0f} min |"
        )
    return "\n".join(linhas)


def main() -> int:
    r = rodar()
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    r.to_csv(SAIDA, index=False)
    conteudo = tabela(r)
    parametros.reescrever(README, conteudo, INICIO, FIM)
    print(conteudo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

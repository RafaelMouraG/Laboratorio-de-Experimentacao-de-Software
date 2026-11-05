"""Q2: poder dos dois testes em efeitos crescentes, no cenário base.

O efeito é o deslocamento do μ do grupo com bot em escala log, então exp(efeito) é quantas vezes a
mediana (e todos os tempos) do grupo com bot fica maior. A grade vai de ×1 (efeito zero, o mesmo
ponto da Q1) a ×100, espaçada em escala log, para a curva do Mann-Whitney sair de 5% e chegar a
100% com o n coletado. O efeito que os dados reais sugerem entra junto, como mais um ponto.

`python -m lab04.simulacao.q2` grava as linhas no `saida/simulacoes.csv` e reescreve a tabela do
`README.md`.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from lab04.simulacao import motor, parametros
from lab04.simulacao.gerador import cenario_base, efeito_observado
from lab04.simulacao.q1 import NOMES, SITUACAO

MULTIPLICADORES = (1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 12, 20, 50, 100)
EFEITOS = tuple(math.log(m) for m in MULTIPLICADORES)
PODER_ALVO = 0.8
README = parametros.LAB / "README.md"
INICIO = "<!-- q2:inicio -->"
FIM = "<!-- q2:fim -->"


def rodar(csv: Path = parametros.CSV) -> pd.DataFrame:
    p = parametros.calcular(csv)
    cenario = cenario_base(p)
    efeitos = sorted({*EFEITOS, efeito_observado(p)})
    return pd.concat([motor.simular(SITUACAO, cenario, e) for e in efeitos], ignore_index=True)


def cruzamento(r: pd.DataFrame, teste: str, alfa: float = 0.05, alvo: float = PODER_ALVO) -> float | None:
    """Primeiro efeito (em log) em que o poder chega a `alvo`, interpolando entre os pontos da grade.

    Devolve None quando o teste não chega ao alvo em nenhum efeito simulado.
    """
    curva = r[(r["teste"] == teste) & (r["alfa"] == alfa)].sort_values("efeito")
    efeito, poder = curva["efeito"].to_numpy(), curva["proporcao"].to_numpy()
    acima = np.flatnonzero(poder >= alvo)
    if not len(acima):
        return None
    i = acima[0]
    if i == 0:
        return float(efeito[0])
    e0, e1, p0, p1 = efeito[i - 1], efeito[i], poder[i - 1], poder[i]
    return float(e0 + (alvo - p0) * (e1 - e0) / (p1 - p0))


def _pp(x: float) -> str:
    return f"{100 * x:.1f}%"


def _vezes(efeito: float) -> str:
    return f"×{math.exp(efeito):.2f}".rstrip("0").rstrip(".")


def tabela(r: pd.DataFrame, observado: float) -> str:
    poder = r.pivot_table(index="efeito", columns=["teste", "alfa"], values="proporcao")
    n_rep = int(r["n_rep"].iloc[0])
    linhas = [
        f"{n_rep} repetições por efeito, cenário base, semente {motor.SEMENTE}. Efeito em log e como "
        "multiplicador da mediana do grupo com bot; a linha em negrito é o efeito dos dados reais.",
        "",
        "| Efeito (log) | Mediana com bot | Welch, α = 5% | Mann-Whitney, α = 5% | Welch, α = 1% | Mann-Whitney, α = 1% |",
        "|---|---|---|---|---|---|",
    ]
    for efeito, l in poder.iterrows():
        celulas = [f"{efeito:.3f}", _vezes(efeito)] + [
            _pp(l[t, a]) for a in (0.05, 0.01) for t in ("welch", "mann_whitney")
        ]
        if math.isclose(efeito, observado):
            celulas = [f"**{c}**" for c in celulas]
        linhas.append("| " + " | ".join(celulas) + " |")
    linhas += ["", f"Efeito em que o poder chega a {PODER_ALVO:.0%} (interpolado entre os pontos da grade):", ""]
    for alfa in (0.05, 0.01):
        for teste in ("welch", "mann_whitney"):
            e = cruzamento(r, teste, alfa)
            onde = (
                f"efeito {e:.2f} no log, mediana {_vezes(e)}" if e is not None
                else f"não chega, nem com a mediana ×{max(MULTIPLICADORES)} (máximo {_pp(poder[teste, alfa].max())})"
            )
            linhas.append(f"- {NOMES[teste]}, α = {alfa:.0%}: {onde}")
    return "\n".join(linhas)


def main() -> int:
    r = rodar()
    motor.gravar(r)
    conteudo = tabela(r, efeito_observado(parametros.calcular()))
    parametros.reescrever(README, conteudo, INICIO, FIM)
    print(conteudo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

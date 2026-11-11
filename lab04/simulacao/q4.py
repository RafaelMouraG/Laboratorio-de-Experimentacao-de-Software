"""Tamanho da amostra: quantos PRs por grupo cada teste precisa para 80% de poder.

Cenário base com o efeito observado nos dados reais (mediana do grupo com bot ×4,76), mudando só o
n, igual nos dois grupos. Responde "se o efeito real for do tamanho que os dados sugerem, quantos
PRs por grupo um novo estudo precisaria coletar".

Cada n é uma situação `amostra_n<n>` no `simulacoes.csv`, com semente própria. O n coletado não
roda de novo: é a linha do cenário base no efeito observado, a mesma que a Q2 e a seção dos dados
reais usam, para os três lugares mostrarem o mesmo poder.

`python -m lab04.simulacao.q4` grava as linhas no `saida/simulacoes.csv` e reescreve a tabela do
`README.md`.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from lab04.simulacao import motor, parametros
from lab04.simulacao.gerador import cenario_base, efeito_observado
from lab04.simulacao.q1 import NOMES, SITUACAO as BASE
from lab04.simulacao.q2 import PODER_ALVO

TAMANHOS = (10, 15, 20, 25, 30, 35, 40, 50, 60, 80, 100, 150, 200, 250, 300, 400, 500)
PREFIXO = "amostra_n"
README = parametros.LAB / "README.md"
INICIO = "<!-- q4:inicio -->"
FIM = "<!-- q4:fim -->"
TESTES = ("welch", "mann_whitney")


def situacao(n: int) -> str:
    return f"{PREFIXO}{n}"


def rodar(csv: Path = parametros.CSV) -> pd.DataFrame:
    """Simula os n da grade, menos o coletado, que já está no cenário base."""
    p = parametros.calcular(csv)
    base = cenario_base(p)
    efeito = efeito_observado(p)
    return pd.concat(
        [motor.simular(situacao(n), replace(base, n=(n, n)), efeito) for n in TAMANHOS if (n, n) != base.n],
        ignore_index=True,
    )


def curva(simulacoes: pd.DataFrame, csv: Path = parametros.CSV) -> pd.DataFrame:
    """Poder por n, uma linha por n × teste × α, juntando o cenário base no n coletado."""
    p = parametros.calcular(csv)
    base = cenario_base(p)
    efeito = efeito_observado(p)
    if "proporcao" not in simulacoes:
        simulacoes = simulacoes.assign(proporcao=simulacoes["rejeicoes"] / simulacoes["n_rep"])
    amostra = simulacoes[simulacoes["situacao"].str.startswith(PREFIXO)]
    amostra = amostra.assign(n=amostra["situacao"].str.removeprefix(PREFIXO).astype(int))
    coletado = simulacoes[
        (simulacoes["situacao"] == BASE) & simulacoes["efeito"].map(lambda e: math.isclose(e, efeito))
    ].assign(n=base.n[0])
    if coletado.empty:
        raise ValueError("falta o efeito observado do cenário base no simulacoes.csv; rode a Q2")
    juntas = pd.concat([amostra, coletado], ignore_index=True)
    faltam = set(TAMANHOS) - set(juntas["n"])
    if faltam:
        raise ValueError(f"faltam os n {sorted(faltam)} no simulacoes.csv; rode a Q4")
    return juntas[juntas["n"].isin(TAMANHOS)].sort_values(["teste", "alfa", "n"], ignore_index=True)


def n_para(c: pd.DataFrame, teste: str, alfa: float = 0.05, alvo: float = PODER_ALVO) -> int | None:
    """Menor n por grupo com poder `alvo`, interpolando entre os pontos da grade e arredondando para cima.

    Devolve None quando o teste não chega ao alvo nem no maior n simulado.
    """
    linhas = c[(c["teste"] == teste) & (c["alfa"] == alfa)].sort_values("n")
    n, poder = linhas["n"].to_numpy(float), linhas["proporcao"].to_numpy(float)
    acima = np.flatnonzero(poder >= alvo)
    if not len(acima):
        return None
    i = acima[0]
    if i == 0:
        return int(n[0])
    n0, n1, p0, p1 = n[i - 1], n[i], poder[i - 1], poder[i]
    # O round tira o resíduo do float (25.000000000000004) antes de arredondar para cima.
    return math.ceil(round(n0 + (alvo - p0) * (n1 - n0) / (p1 - p0), 9))


def tabela(c: pd.DataFrame, csv: Path = parametros.CSV) -> str:
    p = parametros.calcular(csv)
    efeito = efeito_observado(p)
    coletado = cenario_base(p).n[0]
    poder = c.pivot_table(index="n", columns=["teste", "alfa"], values="proporcao")
    n_rep = int(c["n_rep"].iloc[0])
    linhas = [
        f"{n_rep} repetições por n, cenário base no efeito observado ({efeito:.3f} no log, mediana "
        f"×{math.exp(efeito):.2f}), mesmo n nos dois grupos, semente {motor.SEMENTE}. A linha em negrito "
        "é o n coletado, lida do cenário base.",
        "",
        "| n por grupo | Welch, α = 5% | Mann-Whitney, α = 5% | Welch, α = 1% | Mann-Whitney, α = 1% |",
        "|---|---|---|---|---|",
    ]
    for n, l in poder.iterrows():
        celulas = [str(n)] + [f"{100 * l[t, a]:.1f}%" for a in (0.05, 0.01) for t in TESTES]
        if n == coletado:
            celulas = [f"**{x}**" for x in celulas]
        linhas.append("| " + " | ".join(celulas) + " |")
    linhas += ["", f"n por grupo para {PODER_ALVO:.0%} de poder (interpolado entre os pontos da grade):", ""]
    for alfa in (0.05, 0.01):
        for teste in TESTES:
            n = n_para(c, teste, alfa)
            onde = f"{n} PRs por grupo" if n is not None else f"não chega com {max(TAMANHOS)} PRs por grupo"
            linhas.append(f"- {NOMES[teste]}, α = {alfa:.0%}: {onde}")
    return "\n".join(linhas)


def main() -> int:
    todas = motor.gravar(rodar())
    conteudo = tabela(curva(todas))
    parametros.reescrever(README, conteudo, INICIO, FIM)
    print(conteudo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

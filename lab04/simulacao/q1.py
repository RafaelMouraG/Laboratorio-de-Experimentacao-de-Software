"""Q1: erro tipo I dos dois testes no cenário base.

Cenário base do `cenario.md` (n coletado, σ comum) com efeito zero, então H₀ é verdadeira para os
dois testes e toda rejeição é erro tipo I. Roda nos dois α, 5% e 1%.

`python -m lab04.simulacao.q1` grava as linhas no `saida/simulacoes.csv` e reescreve a tabela do
`README.md`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from lab04.simulacao import motor, parametros
from lab04.simulacao.gerador import cenario_base

SITUACAO = "base"
README = parametros.LAB / "README.md"
INICIO = "<!-- q1:inicio -->"
FIM = "<!-- q1:fim -->"
NOMES = {"welch": "t de Welch", "mann_whitney": "Mann-Whitney"}


def rodar(csv: Path = parametros.CSV) -> pd.DataFrame:
    return motor.simular(SITUACAO, cenario_base(parametros.calcular(csv)), efeito=0.0)


def _pp(x: float) -> str:
    return f"{100 * x:.2f}%"


def tabela(r: pd.DataFrame) -> str:
    n_rep = int(r["n_rep"].iloc[0])
    linhas = [
        f"{n_rep} repetições, cenário base com efeito zero (H₀ verdadeira para os dois testes), "
        f"semente {motor.SEMENTE}.",
        "",
        "| Teste | α | Rejeições | Erro tipo I | Faixa esperada (α ± margem de 95%) | Leitura |",
        "|---|---|---|---|---|---|",
    ]
    for _, l in r.sort_values(["alfa", "teste"], ascending=[False, False]).iterrows():
        m = motor.margem(l.alfa, n_rep)
        if l.proporcao < l.alfa - m:
            leitura = "abaixo da faixa"
        elif l.proporcao > l.alfa + m:
            leitura = "acima da faixa"
        else:
            leitura = "dentro da faixa"
        linhas.append(
            f"| {NOMES[l.teste]} | {_pp(l.alfa)} | {l.rejeicoes} | {_pp(l.proporcao)} "
            f"| {_pp(l.alfa - m)} a {_pp(l.alfa + m)} | {leitura} |"
        )
    return "\n".join(linhas)


def main() -> int:
    r = rodar()
    motor.gravar(r)
    conteudo = tabela(r)
    parametros.reescrever(README, conteudo, INICIO, FIM)
    print(conteudo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

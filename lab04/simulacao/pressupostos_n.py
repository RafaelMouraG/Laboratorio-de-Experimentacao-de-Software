"""[Extra] Pressupostos × n: o melhor teste muda com o tamanho da amostra?

Repete erro tipo I e poder de três situações da Q3 (`base`, `assimetria` e `outliers`) com 10, 30,
100 e 200 PRs por grupo. O poder é medido na mediana ×3, o ponto da grade da Q2 em que o
Mann-Whitney tem cerca de 50% de poder no cenário base com o n coletado (47%), para a diferença
entre os testes não começar colada em 0% nem em 100%.

Os pontos que já existem não rodam de novo: o n coletado é a própria situação da Q3 (ou o cenário
base), e o base com n = 10 é o `n_pequeno` da Q3. Os outros rodam com a regra de semente do motor e
o n no nome da combinação (`assimetria_n100`), então nada do `simulacoes.csv` muda.

`python -m lab04.simulacao.pressupostos_n` grava as linhas novas no `saida/tamanho_amostra.csv` e
reescreve a tabela do `README.md`.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pandas as pd

from lab04.simulacao import motor, parametros, q3
from lab04.simulacao.gerador import Cenario, cenario_base
from lab04.simulacao.q1 import SITUACAO as BASE

SITUACOES = (BASE, "assimetria", "outliers")
TAMANHOS = (10, 30, 100, 200)
MULTIPLICADOR = 3
EFEITO = math.log(MULTIPLICADOR)
EFEITOS = (0.0, EFEITO)
SAIDA = parametros.LAB / "saida" / "tamanho_amostra.csv"
COLUNAS = ["situacao", "n", "efeito", "teste", "alfa", "rejeicoes", "n_rep"]
CHAVE = ["situacao", "n", "efeito", "teste", "alfa"]
README = parametros.LAB / "README.md"
INICIO = "<!-- pressupostos_n:inicio -->"
FIM = "<!-- pressupostos_n:fim -->"
TESTES = ("welch", "mann_whitney")


def cenarios(p: dict[str, parametros.Parametros]) -> dict[str, Cenario]:
    q3_situacoes = q3.situacoes(p)
    return {s: cenario_base(p) if s == BASE else q3_situacoes[s] for s in SITUACOES}


def origem(situacao: str, n: int, coletado: int) -> str | None:
    """Situação do `simulacoes.csv` que já tem esse ponto, ou None quando ele precisa rodar."""
    if n == coletado:
        return situacao
    if situacao == BASE and n == q3.N_PEQUENO:
        return "n_pequeno"
    return None


def combinacao(situacao: str, n: int) -> str:
    """Nome que entra no hash da semente: a situação com o n, para não repetir a da Q3."""
    return f"{situacao}_n{n}"


def rodar(csv: Path = parametros.CSV) -> pd.DataFrame:
    """Simula só os pontos que ainda não estão no `simulacoes.csv`."""
    p = parametros.calcular(csv)
    coletado = cenario_base(p).n[0]
    partes = [
        motor.simular(combinacao(s, n), replace(c, n=(n, n)), e).assign(situacao=s, n=n)
        for s, c in cenarios(p).items()
        for n in TAMANHOS if origem(s, n, coletado) is None
        for e in EFEITOS
    ]
    return pd.concat(partes, ignore_index=True)


def gravar(novas: pd.DataFrame, caminho: Path = SAIDA) -> pd.DataFrame:
    return motor.gravar(novas, caminho, COLUNAS, CHAVE)


def curva(
    simulacoes: pd.DataFrame, extras: pd.DataFrame, csv: Path = parametros.CSV
) -> pd.DataFrame:
    """Uma linha por situação × n × efeito × teste × α, juntando os pontos que vêm da Q2 e da Q3."""
    coletado = cenario_base(parametros.calcular(csv)).n[0]
    partes = [extras[COLUNAS]]
    for s in SITUACOES:
        for n in TAMANHOS:
            fonte = origem(s, n, coletado)
            if fonte is None:
                continue
            linhas = simulacoes[
                (simulacoes["situacao"] == fonte)
                & simulacoes["efeito"].map(lambda e: any(math.isclose(e, x, abs_tol=1e-12) for x in EFEITOS))
            ]
            partes.append(linhas.assign(situacao=s, n=n)[COLUNAS])
    juntas = pd.concat(partes, ignore_index=True)
    juntas = juntas[juntas["situacao"].isin(SITUACOES) & juntas["n"].isin(TAMANHOS)]
    esperado = {(s, n, e, t, a) for s in SITUACOES for n in TAMANHOS for e in EFEITOS
                for t in TESTES for a in motor.ALFAS}
    achado = set(juntas[CHAVE].itertuples(index=False, name=None))
    faltam = {(s, n) for s, n, *_ in esperado - achado}
    if faltam:
        raise ValueError(
            f"faltam {sorted(faltam)} no tamanho_amostra.csv ou no simulacoes.csv; "
            "rode a Q3 e o pressupostos_n"
        )
    juntas = juntas.assign(proporcao=juntas["rejeicoes"] / juntas["n_rep"])
    return juntas.sort_values(CHAVE, ignore_index=True)


def vantagem(c: pd.DataFrame, alfa: float = 0.05) -> pd.DataFrame:
    """Poder dos dois testes no efeito da grade e a diferença Mann-Whitney − Welch, por situação e n."""
    poder = c[(c["alfa"] == alfa) & (c["efeito"] == EFEITO)].pivot_table(
        index=["situacao", "n"], columns="teste", values="proporcao"
    )
    return poder.assign(diferenca=poder["mann_whitney"] - poder["welch"]).reset_index()


def _pp(x: float) -> str:
    return f"{100 * x:.1f}%"


def tabela(c: pd.DataFrame) -> str:
    v = vantagem(c).set_index(["situacao", "n"])
    zero = c[(c["alfa"] == 0.05) & (c["efeito"] == 0.0)].pivot_table(
        index=["situacao", "n"], columns="teste", values="proporcao"
    )
    n_rep = int(c["n_rep"].iloc[0])
    linhas = [
        f"{n_rep} repetições por ponto, semente {motor.SEMENTE}, α = 5%, mesmo n nos dois grupos. Poder "
        f"na mediana ×{MULTIPLICADOR}. O n coletado e o `base` com n = {q3.N_PEQUENO} são os pontos da Q2 e da Q3.",
        "",
        "| Situação | n por grupo | Erro tipo I, Welch | Erro tipo I, Mann-Whitney | Poder, Welch | Poder, Mann-Whitney | Mann-Whitney − Welch |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in SITUACOES:
        for n in TAMANHOS:
            l, z = v.loc[(s, n)], zero.loc[(s, n)]
            linhas.append(_linha(s, n, l, z))
    return "\n".join(linhas)


def _linha(s: str, n: int, l: pd.Series, z: pd.Series) -> str:
    return (
        f"| `{s}` | {n} | {_pp(z['welch'])} | {_pp(z['mann_whitney'])} | {_pp(l['welch'])} "
        f"| {_pp(l['mann_whitney'])} | {100 * l['diferenca']:+.1f} p.p. |"
    )


def main() -> int:
    extras = gravar(rodar())
    c = curva(motor.ler(), extras)
    conteudo = tabela(c)
    parametros.reescrever(README, conteudo, INICIO, FIM)
    print(conteudo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

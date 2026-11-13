"""Conferência do modelo: os dois testes com a forma dos PRs reais, em vez da lognormal.

O cenário base sorteia de uma lognormal com σ = 2,1 no log. Esse σ é grande porque os PRs reais
têm muitos merges em menos de uma hora, não porque têm PRs de meses. Só que a lognormal é simétrica
no log: ela devolve o mesmo espalhamento para cima e inventa uma cauda à direita que os dados não
têm. O Welch, que depende da média e do desvio padrão das horas, é quem paga por essa cauda.

Aqui cada conjunto é sorteado, com reposição, dos próprios 60 PRs. Tira-se de cada PR a média do
log do seu grupo, e os 60 resíduos viram uma forma só, comum aos dois grupos. O tempo simulado é
exp(μ + resíduo), com o efeito somado no grupo com bot, igual ao gerador da lognormal. Com efeito
zero os dois grupos saem da mesma distribuição, então H₀ é verdadeira para os dois testes.

O limite é o oposto do da lognormal: nenhum tempo sorteado passa do maior resíduo observado, então
a cauda fica mais curta que a verdadeira e o Welch sai favorecido. A lognormal e a reamostragem
são os dois extremos, e o comportamento real dos testes fica entre eles.

`python -m lab04.simulacao.reamostragem` grava as linhas no `saida/simulacoes.csv`, na situação
`reamostragem`, e reescreve a tabela do `README.md`.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from lab04.simulacao import motor, parametros, q2
from lab04.simulacao.gerador import cenario_base, efeito_observado
from lab04.simulacao.q1 import NOMES, SITUACAO as BASE

SITUACAO = "reamostragem"
README = parametros.LAB / "README.md"
INICIO = "<!-- reamostragem:inicio -->"
FIM = "<!-- reamostragem:fim -->"
TESTES = ("welch", "mann_whitney")


def residuos(csv: Path = parametros.CSV) -> np.ndarray:
    """Log das horas de cada PR menos a média do log do seu grupo, com os dois grupos juntos."""
    prs = pd.read_csv(csv)
    log = np.log(prs["horas_ate_merge"].astype(float))
    return (log - log.groupby(prs["grupo"]).transform("mean")).to_numpy()


def gerar(
    rng: np.random.Generator,
    forma: np.ndarray,
    n: tuple[int, int],
    mu: float,
    efeito: float = 0.0,
    repeticoes: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """Sorteia `repeticoes` conjuntos, em horas, reamostrando `forma` com reposição."""
    com = np.exp(mu + efeito + rng.choice(forma, size=(repeticoes, n[0])))
    sem = np.exp(mu + rng.choice(forma, size=(repeticoes, n[1])))
    return com, sem


def simular(forma: np.ndarray, n: tuple[int, int], mu: float, efeito: float, n_rep: int = motor.N_REP) -> pd.DataFrame:
    """Uma combinação, no formato do `simulacoes.csv`, com a semente derivada como no motor."""
    com, sem = gerar(motor.gerador(SITUACAO, efeito), forma, n, mu, efeito, n_rep)
    linhas = [
        {"situacao": SITUACAO, "efeito": float(efeito), "teste": teste, "alfa": alfa, "rejeicoes": r, "n_rep": n_rep}
        for (teste, alfa), r in motor.rejeicoes(com, sem).items()
    ]
    df = pd.DataFrame(linhas, columns=motor.COLUNAS)
    return df.assign(proporcao=df["rejeicoes"] / df["n_rep"])


def rodar(csv: Path = parametros.CSV) -> pd.DataFrame:
    """Mesmo n, mesmo μ e mesma grade de efeitos do cenário base, para as curvas serem comparáveis."""
    p = parametros.calcular(csv)
    base = cenario_base(p)
    forma = residuos(csv)
    efeitos = sorted({*q2.EFEITOS, efeito_observado(p)})
    return pd.concat([simular(forma, base.n, base.mu, e) for e in efeitos], ignore_index=True)


def cauda(csv: Path = parametros.CSV) -> dict[str, dict[str, float]]:
    """Por grupo: média real das horas, média que a lognormal ajustada implica, e o maior tempo real
    ao lado do percentil 99 da lognormal."""
    prs = pd.read_csv(csv)
    saida = {}
    for grupo, p in parametros.calcular(csv).items():
        horas = prs.loc[prs["grupo"] == grupo, "horas_ate_merge"].astype(float)
        saida[grupo] = {
            "media_real": float(horas.mean()),
            "media_lognormal": math.exp(p.mu + p.sigma ** 2 / 2),
            "maximo_real": float(horas.max()),
            "p99_lognormal": math.exp(p.mu + 2.3263478740408408 * p.sigma),
        }
    return saida


def _taxa(r: pd.DataFrame, teste: str, alfa: float, efeito: float) -> float:
    l = r[(r["teste"] == teste) & (r["alfa"] == alfa) & r["efeito"].map(lambda e: math.isclose(e, efeito, abs_tol=1e-12))]
    return float(l["rejeicoes"].iloc[0] / l["n_rep"].iloc[0])


def tabela(r: pd.DataFrame, base: pd.DataFrame, csv: Path = parametros.CSV) -> str:
    observado = efeito_observado(parametros.calcular(csv))
    n_rep = int(r["n_rep"].iloc[0])
    linhas = [
        "A cauda que a lognormal ajustada implica, ao lado da que os PRs têm:",
        "",
        "| Grupo | Média real (h) | Média da lognormal (h) | Maior tempo real (h) | Percentil 99 da lognormal (h) |",
        "|---|---|---|---|---|",
    ]
    for grupo, c in cauda(csv).items():
        linhas.append(
            f"| {grupo} | {c['media_real']:.0f} | {c['media_lognormal']:.0f} | {c['maximo_real']:.0f} "
            f"| {c['p99_lognormal']:.0f} |"
        )
    linhas += [
        "",
        f"{n_rep} repetições por ponto, n coletado, semente {motor.SEMENTE}. `base` é a lognormal; "
        "`reamostragem` sorteia dos 60 PRs reais.",
        "",
        "| Modelo | Teste | Erro tipo I, α = 5% | Erro tipo I, α = 1% | Poder no efeito observado, α = 5% | α = 1% | Chega a 80% em (α = 5%) |",
        "|---|---|---|---|---|---|---|",
    ]
    for nome, g in ((BASE, base), (SITUACAO, r)):
        g = g if "proporcao" in g else g.assign(proporcao=g["rejeicoes"] / g["n_rep"])
        for teste in TESTES:
            e = q2.cruzamento(g, teste)
            onde = "não chega" if e is None else f"×{math.exp(e):.1f}"
            linhas.append(
                f"| `{nome}` | {NOMES[teste]} | {100 * _taxa(g, teste, 0.05, 0.0):.2f}% "
                f"| {100 * _taxa(g, teste, 0.01, 0.0):.2f}% | {100 * _taxa(g, teste, 0.05, observado):.1f}% "
                f"| {100 * _taxa(g, teste, 0.01, observado):.1f}% | {onde} |"
            )
    return "\n".join(linhas)


def main() -> int:
    r = rodar()
    todas = motor.gravar(r)
    conteudo = tabela(r, todas[todas["situacao"] == BASE])
    parametros.reescrever(README, conteudo, INICIO, FIM)
    print(conteudo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

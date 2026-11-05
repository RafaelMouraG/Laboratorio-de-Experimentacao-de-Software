"""Q3: erro tipo I e poder quando os dados violam os pressupostos.

Quatro situações, cada uma mudando uma coisa no cenário base:

- `assimetria`: σ do log 1,5 vez o σ comum, cauda mais longa que a real.
- `outliers`: 5% dos PRs, nos dois grupos, com o tempo multiplicado por 50, como PRs esquecidos
  abertos por semanas.
- `n_pequeno`: 10 PRs por grupo.
- `dispersoes`: a mesma mediana e o σ real de cada grupo. Aqui as médias diferem com efeito zero,
  então a H₀ do Welch é falsa e a do Mann-Whitney é verdadeira. Entra também o efeito que iguala as
  médias, onde é o contrário (ver `cenario.md`).

Cada situação roda a mesma grade de efeitos da Q2, nos dois α. `python -m lab04.simulacao.q3`
grava as linhas no `saida/simulacoes.csv` e reescreve as tabelas do `README.md`.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from lab04.simulacao import motor, parametros, q2
from lab04.simulacao.gerador import Cenario, cenario_base
from lab04.simulacao.q1 import NOMES, SITUACAO as BASE

FATOR_SIGMA = 1.5
FRACAO_OUTLIERS = 0.05
FATOR_OUTLIERS = 50.0
N_PEQUENO = 10
README = parametros.LAB / "README.md"
INICIO = "<!-- q3:inicio -->"
FIM = "<!-- q3:fim -->"
TESTES = ("welch", "mann_whitney")


def situacoes(p: dict[str, parametros.Parametros]) -> dict[str, Cenario]:
    base = cenario_base(p)
    s = base.sigma[0]
    return {
        "assimetria": Cenario(base.n, base.mu, (FATOR_SIGMA * s, FATOR_SIGMA * s)),
        "outliers": Cenario(base.n, base.mu, base.sigma, FRACAO_OUTLIERS, FATOR_OUTLIERS),
        "n_pequeno": Cenario((N_PEQUENO, N_PEQUENO), base.mu, base.sigma),
        "dispersoes": Cenario(base.n, base.mu, (p["com_bot"].sigma, p["sem_bot"].sigma)),
    }


def descricao(nome: str, c: Cenario) -> str:
    return {
        "assimetria": f"σ = {c.sigma[0]:.2f} nos dois grupos",
        "outliers": f"{c.outliers:.0%} dos PRs × {c.fator:.0f}",
        "n_pequeno": f"n = {c.n[0]} por grupo",
        "dispersoes": f"mesma mediana, σ = {c.sigma[0]:.2f} com bot e {c.sigma[1]:.2f} sem",
    }[nome]


def efeito_medias_iguais(c: Cenario) -> float:
    """Deslocamento do μ do grupo com bot que iguala as médias: exp(μ + σ²/2) igual nos dois."""
    return (c.sigma[1] ** 2 - c.sigma[0] ** 2) / 2


def efeitos(nome: str, c: Cenario) -> list[float]:
    extra = {efeito_medias_iguais(c)} if nome == "dispersoes" else set()
    return sorted({*q2.EFEITOS, *extra})


def rodar(csv: Path = parametros.CSV) -> pd.DataFrame:
    return pd.concat(
        [motor.simular(nome, c, e)
         for nome, c in situacoes(parametros.calcular(csv)).items() for e in efeitos(nome, c)],
        ignore_index=True,
    )


def _taxa(r: pd.DataFrame, teste: str, alfa: float) -> str:
    """Taxa de rejeição com seta quando sai da faixa α ± margem de 95% da Q1."""
    l = r[(r["teste"] == teste) & (r["alfa"] == alfa)].iloc[0]
    m = motor.margem(alfa, int(l.n_rep))
    seta = " ↓" if l.proporcao < alfa - m else " ↑" if l.proporcao > alfa + m else ""
    return f"{100 * l.proporcao:.1f}%{seta}"


def _poder(r: pd.DataFrame, teste: str, efeito: float) -> str:
    l = r[(r["teste"] == teste) & (r["alfa"] == 0.05) & r["efeito"].map(lambda e: math.isclose(e, efeito))]
    return f"{100 * l['proporcao'].iloc[0]:.0f}%"


def _cruza(r: pd.DataFrame, teste: str) -> str:
    e = q2.cruzamento(r[r["efeito"] >= 0], teste)
    return "não chega" if e is None else f"×{math.exp(e):.1f}"


def tabela(r: pd.DataFrame, base: pd.DataFrame, cenarios: dict[str, Cenario]) -> str:
    grupos = {BASE: base, **{n: r[r["situacao"] == n] for n in cenarios}}
    desc = {BASE: "cenário base, para comparar", **{n: descricao(n, c) for n, c in cenarios.items()}}
    n_rep = int(r["n_rep"].iloc[0])
    linhas = [
        f"{n_rep} repetições por ponto, semente {motor.SEMENTE}. ↓ e ↑: fora da faixa α ± margem de 95%.",
        "",
        "**Efeito zero.** É erro tipo I quando a H₀ do teste é verdadeira; em `dispersoes` a do Welch é "
        "falsa (marcado com \\*).",
        "",
        "| Situação | O que muda | Welch, α = 5% | Mann-Whitney, α = 5% | Welch, α = 1% | Mann-Whitney, α = 1% |",
        "|---|---|---|---|---|---|",
    ]
    for nome, g in grupos.items():
        zero = g[g["efeito"] == 0.0]
        marca = "\\*" if nome == "dispersoes" else ""
        celulas = [f"{_taxa(zero, t, a)}{marca if t == 'welch' else ''}" for a in (0.05, 0.01) for t in TESTES]
        linhas.append(f"| `{nome}` | {desc[nome]} | " + " | ".join(celulas) + " |")

    linhas += [
        "",
        "**Poder, α = 5%.** Na mediana ×2 e ×5 e o efeito em que cada teste chega a 80%.",
        "",
        "| Situação | Welch, ×2 | Mann-Whitney, ×2 | Welch, ×5 | Mann-Whitney, ×5 | Welch chega a 80% em | Mann-Whitney chega a 80% em |",
        "|---|---|---|---|---|---|---|",
    ]
    for nome, g in grupos.items():
        celulas = [_poder(g, t, math.log(m)) for m in (2, 5) for t in TESTES] + [_cruza(g, t) for t in TESTES]
        linhas.append(f"| `{nome}` | " + " | ".join(celulas) + " |")

    disp = cenarios["dispersoes"]
    e_igual = efeito_medias_iguais(disp)
    g = grupos["dispersoes"]
    linhas += [
        "",
        f"**`dispersoes`, os dois pontos.** Com efeito zero as medianas são iguais e a média do grupo com "
        f"bot é ×{math.exp((disp.sigma[0] ** 2 - disp.sigma[1] ** 2) / 2):.2f} a do sem bot. Com efeito "
        f"{e_igual:.3f} (mediana com bot ×{math.exp(e_igual):.2f}) as médias são iguais.",
        "",
        "| Ponto | H₀ do Welch | H₀ do Mann-Whitney | Welch, α = 5% | Mann-Whitney, α = 5% | Welch, α = 1% | Mann-Whitney, α = 1% |",
        "|---|---|---|---|---|---|---|",
    ]
    for rotulo, e, hw, hm in [("medianas iguais", 0.0, "falsa", "verdadeira"),
                              ("médias iguais", e_igual, "verdadeira", "falsa")]:
        ponto = g[g["efeito"].map(lambda x: math.isclose(x, e))]
        celulas = [_taxa(ponto, t, a) for a in (0.05, 0.01) for t in TESTES]
        linhas.append(f"| {rotulo} | {hw} | {hm} | " + " | ".join(celulas) + " |")
    return "\n".join(linhas)


def main() -> int:
    r = rodar()
    motor.gravar(r)
    base = q2.rodar()
    conteudo = tabela(r, base, situacoes(parametros.calcular()))
    parametros.reescrever(README, conteudo, INICIO, FIM)
    print(conteudo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

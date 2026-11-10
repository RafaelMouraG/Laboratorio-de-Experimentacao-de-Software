"""Os dois testes nos PRs coletados, com o poder que a Q2 dá para o efeito observado.

Usa as mesmas funções das simulações, sobre as horas brutas do `prs.csv`. O poder não é
recalculado: sai da linha do cenário base no `simulacoes.csv` com o efeito observado, que a Q2
já põe na grade. Como esse efeito é a diferença dos μ dos grupos reais, o poder responde "se o
efeito for do tamanho que os dados sugerem, com 30 PRs por grupo, quantas vezes cada teste o vê".

`python -m lab04.simulacao.reais` reescreve a tabela do `README.md`. O dashboard chama `rodar`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from lab04.simulacao import motor, parametros
from lab04.simulacao.gerador import efeito_observado
from lab04.simulacao.q1 import NOMES, SITUACAO
from lab04.simulacao.testes import delta_cliff, g_hedges, mann_whitney, welch

ALFAS = (0.05, 0.01)
README = parametros.LAB / "README.md"
INICIO = "<!-- reais:inicio -->"
FIM = "<!-- reais:fim -->"


@dataclass(frozen=True)
class Teste:
    teste: str
    simbolo: str
    estatistica: float
    p: float
    efeito_nome: str
    efeito: float
    poder: dict[float, float]

    def rejeita(self, alfa: float) -> bool:
        return self.p < alfa


@dataclass(frozen=True)
class Reais:
    n: dict[str, int]
    mediana: dict[str, float]
    media: dict[str, float]
    efeito_log: float
    testes: tuple[Teste, Teste]

    @property
    def diferenca_medianas(self) -> float:
        return self.mediana["com_bot"] - self.mediana["sem_bot"]


def poder_no_efeito(simulacoes: pd.DataFrame, efeito: float, teste: str, alfa: float) -> float:
    """Proporção de rejeições do cenário base no efeito da grade mais próximo de `efeito`."""
    curva = simulacoes[
        (simulacoes["situacao"] == SITUACAO) & (simulacoes["teste"] == teste) & (simulacoes["alfa"] == alfa)
    ]
    linha = curva.iloc[(curva["efeito"] - efeito).abs().argsort().iloc[0]]
    if not math.isclose(linha["efeito"], efeito, abs_tol=1e-9):
        raise ValueError(f"o efeito observado {efeito:.3f} não está no simulacoes.csv; rode a Q2")
    return float(linha["rejeicoes"] / linha["n_rep"])


def rodar(csv: Path = parametros.CSV, simulacoes: Path = motor.SAIDA) -> Reais:
    prs = pd.read_csv(csv)
    horas = {g: h.to_numpy(float) for g, h in prs.groupby("grupo")["horas_ate_merge"]}
    com, sem = horas["com_bot"], horas["sem_bot"]
    efeito = efeito_observado(parametros.calcular(csv))
    sim = motor.ler(simulacoes)

    def poder(teste: str) -> dict[float, float]:
        return {a: poder_no_efeito(sim, efeito, teste, a) for a in ALFAS}

    w, m = welch(com, sem), mann_whitney(com, sem)
    return Reais(
        n={g: len(h) for g, h in horas.items()},
        mediana={g: float(np.median(h)) for g, h in horas.items()},
        media={g: float(h.mean()) for g, h in horas.items()},
        efeito_log=efeito,
        testes=(
            Teste("welch", "t", float(w.estatistica), float(w.p), "g de Hedges",
                  float(g_hedges(com, sem)), poder("welch")),
            Teste("mann_whitney", "U", float(m.estatistica), float(m.p), "δ de Cliff",
                  float(delta_cliff(com, sem)), poder("mann_whitney")),
        ),
    )


def estatistica(t: Teste) -> str:
    """t com três casas; U é soma de contagens de pares, então sai inteiro (ou com meio, se houver empate)."""
    valor = f"{t.estatistica:.3f}" if t.simbolo == "t" else f"{t.estatistica:g}"
    return f"{t.simbolo} = {valor}"


def conclusao(t: Teste) -> str:
    """Decisão nos dois α, no vocabulário da H₀ de cada teste."""
    h0 = "médias iguais" if t.teste == "welch" else "nenhum grupo tende a demorar mais"
    decisoes = [f"{'rejeitada' if t.rejeita(a) else 'não rejeitada'} a {a:.0%}" for a in ALFAS]
    return f"H₀ ({h0}) {', '.join(decisoes)}"


def tabela(r: Reais) -> str:
    linhas = [
        f"{r.n['com_bot']} PRs com bot e {r.n['sem_bot']} sem, horas brutas. Mediana {r.mediana['com_bot']:.1f} h "
        f"com bot e {r.mediana['sem_bot']:.1f} h sem ({r.diferenca_medianas:+.1f} h); média "
        f"{r.media['com_bot']:.1f} h e {r.media['sem_bot']:.1f} h. Poder lido na Q2, no efeito observado "
        f"({r.efeito_log:.3f} no log, mediana ×{math.exp(r.efeito_log):.2f}).",
        "",
        "| Teste | Estatística | p-valor | Tamanho de efeito | Conclusão | Poder, α = 5% | Poder, α = 1% |",
        "|---|---|---|---|---|---|---|",
    ]
    for t in r.testes:
        linhas.append(
            f"| {NOMES[t.teste]} | {estatistica(t)} | {t.p:.4f} | {t.efeito_nome} = {t.efeito:.3f} "
            f"| {conclusao(t)} | {t.poder[0.05]:.1%} | {t.poder[0.01]:.1%} |"
        )
    return "\n".join(linhas)


def main() -> int:
    conteudo = tabela(rodar())
    parametros.reescrever(README, conteudo, INICIO, FIM)
    print(conteudo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

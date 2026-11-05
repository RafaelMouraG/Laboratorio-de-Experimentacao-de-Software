"""Gerador dos dados simulados: tempo até o merge de PRs com e sem CodeRabbit.

Cada grupo é uma lognormal. O efeito é somado ao μ do grupo com bot, ou seja, multiplica todos os
tempos desse grupo por exp(efeito). Efeito zero com o mesmo σ nos dois grupos é H₀ verdadeira para
o Welch e para o Mann-Whitney ao mesmo tempo (ver `cenario.md`).

Tudo sai em matriz, uma linha por conjunto de dados, para as 10.000 repetições rodarem sem laço.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from lab04.simulacao.parametros import Parametros, sigma_comum


@dataclass(frozen=True)
class Cenario:
    """O que o gerador precisa para um cenário: n e σ de cada grupo e o μ de referência.

    `outliers` é a fração de PRs, nos dois grupos, que tem o tempo multiplicado por `fator`
    depois de sorteado (ver `contaminar`). Zero deixa a lognormal pura.
    """

    n: tuple[int, int]
    mu: float
    sigma: tuple[float, float]
    outliers: float = 0.0
    fator: float = 1.0


def cenario_base(parametros: dict[str, Parametros]) -> Cenario:
    """n coletado, μ do grupo sem bot e o σ comum dos dois grupos.

    O μ só fixa a escala. Welch e Mann-Whitney não mudam quando todos os tempos são multiplicados
    pela mesma constante, então qualquer μ daria os mesmos p-valores com a mesma semente.
    """
    com, sem = parametros["com_bot"], parametros["sem_bot"]
    s = sigma_comum(parametros)
    return Cenario(n=(com.n, sem.n), mu=sem.mu, sigma=(s, s))


def efeito_observado(parametros: dict[str, Parametros]) -> float:
    """Diferença entre os μ dos grupos reais, em escala log."""
    return parametros["com_bot"].mu - parametros["sem_bot"].mu


def _par(valor) -> tuple:
    return tuple(valor) if np.ndim(valor) else (valor, valor)


def gerar(
    rng: np.random.Generator,
    n: int | tuple[int, int],
    mu: float,
    sigma: float | tuple[float, float],
    efeito: float = 0.0,
    repeticoes: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """Sorteia `repeticoes` conjuntos de dados, em horas.

    `n` e `sigma` aceitam um valor para os dois grupos ou um par (com_bot, sem_bot). Devolve
    `(com_bot, sem_bot)`, cada um com shape `(repeticoes, n do grupo)`.
    """
    n_com, n_sem = _par(n)
    s_com, s_sem = _par(sigma)
    if min(n_com, n_sem) < 2:
        raise ValueError("cada grupo precisa de pelo menos 2 PRs")
    if min(s_com, s_sem) <= 0:
        raise ValueError("sigma precisa ser positivo")
    com = rng.lognormal(mu + efeito, s_com, size=(repeticoes, n_com))
    sem = rng.lognormal(mu, s_sem, size=(repeticoes, n_sem))
    return com, sem


def contaminar(rng: np.random.Generator, horas: np.ndarray, fracao: float, fator: float) -> np.ndarray:
    """Multiplica por `fator` cada tempo com probabilidade `fracao`, imitando PRs esquecidos abertos.

    O sorteio é PR a PR, então o número de outliers varia entre os conjuntos, como varia na prática.
    Aplicado aos dois grupos com a mesma fração, mantém H₀ verdadeira com efeito zero.
    """
    if not 0 <= fracao < 1:
        raise ValueError("fracao precisa estar em [0, 1)")
    if fator <= 0:
        raise ValueError("fator precisa ser positivo")
    return np.where(rng.random(horas.shape) < fracao, horas * fator, horas)

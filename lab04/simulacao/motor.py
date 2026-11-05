"""Motor das simulações: repete o gerador e os dois testes e conta as rejeições.

A Q1, a Q2 e a Q3 só mudam a situação (n, μ, σ) e o efeito. Em cada repetição o Welch e o
Mann-Whitney recebem exatamente os mesmos dados, e os dois α saem dos mesmos p-valores.

Sementes: cada combinação (situação, efeito) tem um gerador próprio, derivado da semente principal
e do nome da combinação. Rodar uma situação a mais, ou em outra ordem, não muda as outras, e o
efeito zero da Q2 sai idêntico ao da Q1.

Saída em `lab04/saida/simulacoes.csv`, formato longo, uma linha por situação × efeito × teste × α.
`gravar` troca só as linhas das combinações que acabaram de rodar, então cada questão escreve a sua
parte sem apagar a das outras.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np
import pandas as pd

from lab04.simulacao import parametros
from lab04.simulacao.gerador import Cenario, contaminar, gerar
from lab04.simulacao.testes import mann_whitney, welch

SEMENTE = 42
N_REP = 10_000
ALFAS = (0.05, 0.01)
TESTES = {"welch": welch, "mann_whitney": mann_whitney}
COLUNAS = ["situacao", "efeito", "teste", "alfa", "rejeicoes", "n_rep"]
CHAVE = ["situacao", "efeito", "teste", "alfa"]
SAIDA = parametros.LAB / "saida" / "simulacoes.csv"
Z_95 = 1.959963984540054


def gerador(situacao: str, efeito: float, semente: int = SEMENTE) -> np.random.Generator:
    """Gerador da combinação, derivado da semente principal.

    O hash é do texto `situacao|efeito`, com o efeito em `repr`, que é exato para o float. O
    `hash()` do Python muda a cada processo, por isso o sha256.
    """
    texto = f"{situacao}|{float(efeito)!r}".encode()
    chave = int.from_bytes(hashlib.sha256(texto).digest()[:8], "big")
    return np.random.default_rng([semente, chave])


def rejeicoes(com: np.ndarray, sem: np.ndarray, alfas=ALFAS) -> dict[tuple[str, float], int]:
    """Quantas linhas cada teste rejeita, em cada α. Uma linha da matriz é um conjunto de dados."""
    contagem = {}
    for nome, teste in TESTES.items():
        p = teste(com, sem).p
        for alfa in alfas:
            contagem[nome, alfa] = int(np.count_nonzero(p < alfa))
    return contagem


def simular(
    situacao: str,
    cenario: Cenario,
    efeito: float = 0.0,
    alfas=ALFAS,
    n_rep: int = N_REP,
    semente: int = SEMENTE,
) -> pd.DataFrame:
    """Roda `n_rep` repetições de uma combinação e devolve as linhas do `simulacoes.csv`.

    A coluna `proporcao` (rejeições / n_rep) vem junto para uso direto, mas não vai para o CSV.
    """
    rng = gerador(situacao, efeito, semente)
    com, sem = gerar(rng, cenario.n, cenario.mu, cenario.sigma, efeito, repeticoes=n_rep)
    if cenario.outliers:
        com = contaminar(rng, com, cenario.outliers, cenario.fator)
        sem = contaminar(rng, sem, cenario.outliers, cenario.fator)
    linhas = [
        {"situacao": situacao, "efeito": float(efeito), "teste": teste, "alfa": alfa,
         "rejeicoes": r, "n_rep": n_rep}
        for (teste, alfa), r in rejeicoes(com, sem, alfas).items()
    ]
    df = pd.DataFrame(linhas, columns=COLUNAS)
    return df.assign(proporcao=df["rejeicoes"] / df["n_rep"])


def margem(p: float, n_rep: int = N_REP) -> float:
    """Meia largura do intervalo de 95% de uma proporção p estimada com n_rep repetições.

    Em torno de α = 5% com 10.000 repetições dá cerca de 0,43 ponto percentual: uma taxa observada
    fora de α ± margem é um desvio real do teste, não sorteio.
    """
    return Z_95 * math.sqrt(p * (1 - p) / n_rep)


def ler(caminho: Path = SAIDA) -> pd.DataFrame:
    """Lê o `simulacoes.csv` com os floats exatos.

    O leitor padrão do pandas pode errar o último bit de um float, e aí o efeito lido não bate com
    o da grade: `gravar` duplicaria a linha em vez de trocar, e a busca por efeito falharia.
    """
    return pd.read_csv(caminho, float_precision="round_trip")


def gravar(novas: pd.DataFrame, caminho: Path = SAIDA) -> pd.DataFrame:
    """Junta `novas` ao CSV, trocando as linhas com a mesma situação, efeito, teste e α."""
    novas = novas[COLUNAS]
    if caminho.exists():
        antigas = ler(caminho)
        chaves = pd.MultiIndex.from_frame(novas[CHAVE])
        antigas = antigas[~pd.MultiIndex.from_frame(antigas[CHAVE]).isin(chaves)]
        novas = pd.concat([antigas, novas], ignore_index=True)
    novas = novas.sort_values(CHAVE, ignore_index=True)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    novas.to_csv(caminho, index=False)
    return novas

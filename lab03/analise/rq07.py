"""RQ 07: o quanto a classificação DORA depende da definição operacional.

Execute da raiz do repositório com ``python -m lab03.analise.rq07``.

Três combinações, todas com a regra da C1 (mediana das três notas, arredondada para baixo):

| Combinação | Unidade de deploy | Lead time | CFR |
|---|---|---|---|
| C1 (referência) | release | (a) | (a) |
| C2 | release + pré-release | (b) | (b) |
| C3 | tag | (b) | (a) |

A C1 vem de ``classificacao_c1.csv`` (#109). A C2 e a C3 vêm de ``metricas_c2.csv`` e
``metricas_c3.csv``, que ``python -m lab03.pipeline.alternativas`` grava com as funções de
``lab03/metricas``. A CFR (a) e o tempo de recuperação não dependem da unidade de deploy e saem do
``metricas.csv``. Sem o ``metricas_c3.csv``, os pares com a C3 ficam de fora.
"""

from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

from lab03.analise.comum import DADOS, SAIDA, salvar_figura, salvar_tabela
from lab03.metricas.classificacao import classificacao_geral

FAIXAS = (1, 2, 3, 4)
NOMES = {4: "Elite", 3: "High", 2: "Medium", 1: "Low"}


def comparar(a: pd.Series, b: pd.Series) -> dict:
    """Compara duas classificações indexadas por repo.

    Só entram os repos classificados nas duas. Devolve n, quantos e que % mudaram de categoria e o
    kappa de Cohen com peso linear, em que trocar Elite por Low pesa mais que Elite por High.
    """
    juntas = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    n = len(juntas)
    if n == 0:
        return {"n": 0, "mudaram": 0, "pct_mudaram": float("nan"), "kappa": float("nan")}
    x, y = juntas["a"].astype(int), juntas["b"].astype(int)
    mudaram = int((x != y).sum())
    if mudaram == 0:
        kappa = 1.0  # concordância total; o sklearn devolve NaN quando só há uma categoria
    else:
        kappa = float(cohen_kappa_score(x, y, labels=list(FAIXAS), weights="linear"))
    return {"n": n, "mudaram": mudaram, "pct_mudaram": mudaram / n * 100, "kappa": kappa}


def _geral(*notas: pd.Series) -> pd.Series:
    linhas = pd.concat(notas, axis=1)
    valores = [classificacao_geral(None if pd.isna(v) else int(v) for v in linha) for linha in linhas.values]
    return pd.Series(valores, index=linhas.index, dtype="Float64")


def carregar_combinacoes(dados: Path = DADOS, saida: Path = SAIDA) -> pd.DataFrame:
    """Uma linha por repo, com a classificação geral de cada combinação e as notas de cada métrica."""
    c1 = pd.read_csv(saida / "classificacao_c1.csv").set_index("repo")
    metricas = pd.read_csv(dados / "metricas.csv").set_index("repo")
    tabela = pd.DataFrame(index=c1.index)
    tabela["C1"] = c1["classificacao_geral"]
    tabela["freq_C1"] = c1["faixa_releases"]
    tabela["lead_a_C1"] = c1["faixa_lead_time_release"]
    tabela["lead_b_C1"] = metricas["faixa_lead_time_commit"]
    tabela["cfr_a"] = metricas["faixa_cfr_ci"]
    tabela["cfr_b_C1"] = metricas["faixa_cfr_entrega"]

    for combinacao, arquivo, cfr in (("C2", "metricas_c2.csv", "cfr_b"), ("C3", "metricas_c3.csv", "cfr_a")):
        caminho = dados / arquivo
        if not caminho.exists():
            print(f"{arquivo} não existe; a {combinacao} fica de fora", file=sys.stderr)
            continue
        alternativa = pd.read_csv(caminho).set_index("repo").reindex(tabela.index)
        tabela[f"freq_{combinacao}"] = alternativa["faixa_frequencia"]
        tabela[f"lead_b_{combinacao}"] = alternativa["faixa_lead_time_commit"]
        tabela[f"cfr_b_{combinacao}"] = alternativa["faixa_cfr_entrega"]
        nota_cfr = tabela["cfr_a"] if cfr == "cfr_a" else tabela[f"cfr_b_{combinacao}"]
        tabela[combinacao] = _geral(tabela[f"freq_{combinacao}"], tabela[f"lead_b_{combinacao}"], nota_cfr)
    return tabela


def comparar_combinacoes(tabela: pd.DataFrame) -> pd.DataFrame:
    presentes = [c for c in ("C1", "C2", "C3") if c in tabela]
    return pd.DataFrame([{"par": f"{a} x {b}", **comparar(tabela[a], tabela[b])}
                         for a, b in combinations(presentes, 2)])


# (escolha de definição, métrica, coluna de um lado, coluna do outro)
ESCOLHAS = (
    ("unidade: release x release + pré", "frequência", "freq_C1", "freq_C2"),
    ("unidade: release x tag", "frequência", "freq_C1", "freq_C3"),
    ("lead time: (a) x (b), unidade release", "lead time", "lead_a_C1", "lead_b_C1"),
    ("lead time (b): release x release + pré", "lead time", "lead_b_C1", "lead_b_C2"),
    ("lead time (b): release x tag", "lead time", "lead_b_C1", "lead_b_C3"),
    ("CFR: (a) x (b), unidade release", "CFR", "cfr_a", "cfr_b_C1"),
    ("CFR (b): release x release + pré", "CFR", "cfr_b_C1", "cfr_b_C2"),
)


def comparar_metricas(tabela: pd.DataFrame) -> pd.DataFrame:
    """A mesma comparação faixa a faixa, mudando uma escolha de cada vez."""
    linhas = []
    for escolha, metrica, a, b in ESCOLHAS:
        if a in tabela and b in tabela:
            linhas.append({"escolha": escolha, "metrica": metrica, **comparar(tabela[a], tabela[b])})
    return pd.DataFrame(linhas)


def transicao(a: pd.Series, b: pd.Series) -> pd.DataFrame:
    """Matriz de contagem, linhas em ``a`` e colunas em ``b``, de Elite para Low."""
    juntas = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna().astype(int)
    ordem = list(reversed(FAIXAS))
    return pd.crosstab(juntas["a"], juntas["b"]).reindex(index=ordem, columns=ordem, fill_value=0)


def figura_transicoes(tabela: pd.DataFrame):
    pares = [(b, transicao(tabela["C1"], tabela[b])) for b in ("C2", "C3") if b in tabela]
    fig, eixos = plt.subplots(1, len(pares), figsize=(4.2 * len(pares), 3.8), squeeze=False)
    rotulos = [NOMES[f] for f in reversed(FAIXAS)]
    for eixo, (destino, matriz) in zip(eixos[0], pares):
        valores = matriz.to_numpy()
        eixo.imshow(valores, cmap="Greys")
        limite = valores.max() / 2 if valores.size else 0
        for i, j in np.ndindex(valores.shape):
            eixo.text(j, i, str(valores[i, j]), ha="center", va="center", fontsize=10,
                      color="white" if valores[i, j] > limite else "black")
        eixo.set_xticks(range(4), rotulos)
        eixo.set_yticks(range(4), rotulos)
        eixo.set_xlabel(destino)
        eixo.set_ylabel("C1")
    fig.tight_layout()
    return fig


def main() -> int:
    tabela = carregar_combinacoes()
    pares = comparar_combinacoes(tabela)
    metricas = comparar_metricas(tabela)
    salvar_tabela(pares, "rq07_pares")
    salvar_tabela(metricas, "rq07_metricas")
    for destino in ("C2", "C3"):
        if destino in tabela:
            salvar_tabela(transicao(tabela["C1"], tabela[destino]).rename(index=NOMES, columns=NOMES)
                          .rename_axis(index="C1", columns=None).reset_index(), f"rq07_transicao_c1_{destino.lower()}")
    fig = figura_transicoes(tabela)
    salvar_figura(fig, "rq07_transicoes")
    plt.close(fig)

    print("Pares de combinações")
    print(pares.to_string(index=False))
    print("\nUma escolha de cada vez")
    print(metricas.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

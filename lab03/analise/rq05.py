"""RQ 05: frequência de deploy × taxa de falha.

Execute da raiz do repositório com ``python -m lab03.analise.rq05``.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import spearmanr

from lab03.analise.comum import carregar, salvar_figura, salvar_tabela

FREQUENCIA = "releases_por_semana"
VARIANTES = {
    "cfr_ci": "CFR (a)",
    "cfr_entrega": "CFR (b)",
}


def correlacao(df: pd.DataFrame, x: str, y: str) -> dict:
    """Spearman entre ``x`` e ``y``.

    Linhas sem uma das duas colunas ficam de fora e são contadas em ``ausentes``.
    """
    validos = df[[x, y]].dropna()
    n = len(validos)
    if n < 3:
        raise ValueError(f"Spearman entre {x} e {y} precisa de pelo menos três repositórios")
    rho, p_valor = spearmanr(validos[x], validos[y])
    return {
        "x": x,
        "y": y,
        "n": n,
        "ausentes": len(df) - n,
        "rho": float(rho),
        "p_valor": float(p_valor),
    }


def correlacoes(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por variante e a checagem da (b) sem os repositórios com CFR (b) = 0."""
    linhas = [{"recorte": "todos", **correlacao(df, FREQUENCIA, cfr)} for cfr in VARIANTES]
    sem_zeros = df[df["cfr_entrega"] != 0]
    linhas.append({"recorte": "sem_cfr_zero", **correlacao(sem_zeros, FREQUENCIA, "cfr_entrega")})
    return pd.DataFrame(linhas)


def zeros(df: pd.DataFrame) -> pd.DataFrame:
    """Quantos repositórios têm cada CFR exatamente igual a 0."""
    return pd.DataFrame([
        {"metrica": cfr, "zeros": int((df[cfr] == 0).sum()), "n": int(df[cfr].notna().sum())}
        for cfr in VARIANTES
    ])


def dispersao(df: pd.DataFrame, tabela: pd.DataFrame):
    """Um painel por variante, com a frequência em escala log no eixo x."""
    fig, eixos = plt.subplots(1, len(VARIANTES), figsize=(4.2 * len(VARIANTES), 3.4), sharex=True)
    todos = tabela[tabela["recorte"] == "todos"].set_index("y")
    for eixo, (cfr, nome) in zip(eixos, VARIANTES.items()):
        validos = df[[FREQUENCIA, cfr]].dropna()
        eixo.scatter(validos[FREQUENCIA], validos[cfr], s=10, alpha=0.5)
        eixo.set_xscale("log")
        linha = todos.loc[cfr]
        eixo.set_title(f"{nome}: ρ = {linha['rho']:.2f}, p = {linha['p_valor']:.3g}, n = {linha['n']}", fontsize=9)
        eixo.set_xlabel("Releases por semana (log)", fontsize=8)
        eixo.set_ylabel(nome, fontsize=8)
        eixo.tick_params(labelsize=8)
    fig.tight_layout()
    return fig


def main() -> int:
    df = carregar()
    tabela = correlacoes(df)
    contagem = zeros(df)

    salvar_tabela(tabela, "rq05_correlacoes")
    salvar_tabela(contagem, "rq05_zeros")
    fig = dispersao(df, tabela)
    salvar_figura(fig, "rq05_dispersao")
    plt.close(fig)

    print("RQ 05: Spearman entre releases por semana e CFR")
    print(tabela.to_string(index=False))
    print(contagem.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

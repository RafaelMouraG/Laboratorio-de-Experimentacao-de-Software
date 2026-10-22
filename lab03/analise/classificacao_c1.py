"""Distribuição e composição da classificação DORA de referência C1.

Execute da raiz do repositório com ``python -m lab03.analise.classificacao_c1``.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from lab03.analise.comum import carregar, salvar_figura, salvar_tabela

NOTAS_C1 = {
    "faixa_releases": "Releases por semana",
    "faixa_lead_time_release": "Lead time (a)",
    "faixa_cfr_ci": "CFR (a)",
}
NOTAS_DORA = {
    **NOTAS_C1,
    "faixa_recuperacao": "Tempo de recuperação",
}
FAIXAS = {4: "Elite", 3: "High", 2: "Medium", 1: "Low"}
ORDEM_FAIXAS = ("Low", "Medium", "High", "Elite", "Sem nota")
ORDEM_GERAL = ("Low", "Medium", "High", "Elite", "Sem classificação")


def dados_c1(df: pd.DataFrame) -> pd.DataFrame:
    """Seleciona um registro por repositório com as quatro faixas e a geral C1."""
    colunas = ["repo", *NOTAS_DORA, "classificacao_geral"]
    return df[colunas].copy()


def distribuicao_geral(df: pd.DataFrame) -> pd.DataFrame:
    """Conta cada categoria geral e calcula percentual sobre todos os repositórios."""
    total = len(df)
    contagens = df["classificacao_geral"].value_counts()
    linhas = []
    for nota, categoria in sorted(FAIXAS.items(), reverse=True):
        quantidade = int(contagens.get(nota, 0))
        linhas.append({
            "classificacao_geral": categoria,
            "nota": nota,
            "repositorios": quantidade,
            "percentual": quantidade / total * 100 if total else float("nan"),
        })
    sem_classificacao = int(df["classificacao_geral"].isna().sum())
    linhas.append({
        "classificacao_geral": "Sem classificação",
        "nota": pd.NA,
        "repositorios": sem_classificacao,
        "percentual": sem_classificacao / total * 100 if total else float("nan"),
    })
    return pd.DataFrame(linhas)


def contagem_notas(df: pd.DataFrame) -> pd.DataFrame:
    """Resume a cobertura das quatro métricas e dos três componentes de C1."""
    classificacao = df["classificacao_geral"].notna()
    coberturas = (
        ("quatro_metricas", df[list(NOTAS_DORA)].notna().sum(axis=1)),
        ("componentes_c1", df[list(NOTAS_C1)].notna().sum(axis=1)),
    )
    linhas = []
    for escopo, quantidade_notas in coberturas:
        for n_notas in range(len(NOTAS_DORA) if escopo == "quatro_metricas" else len(NOTAS_C1), -1, -1):
            selecionados = quantidade_notas.eq(n_notas)
            n = int(selecionados.sum())
            linhas.append({
                "escopo": escopo,
                "notas_validas": n_notas,
                "repositorios": n,
                "classificados": int((selecionados & classificacao).sum()),
                "sem_classificacao": int((selecionados & ~classificacao).sum()),
            })
    return pd.DataFrame(linhas)


def tabela_cruzada(df: pd.DataFrame) -> pd.DataFrame:
    """Cruza as faixas de cada métrica com a categoria geral C1."""
    categoria_geral = df["classificacao_geral"].map(FAIXAS).fillna("Sem classificação")
    linhas = []
    for coluna, metrica in NOTAS_DORA.items():
        faixa = df[coluna].map(FAIXAS).fillna("Sem nota")
        cruzamento = pd.crosstab(faixa, categoria_geral)
        cruzamento = cruzamento.reindex(
            index=ORDEM_FAIXAS,
            columns=ORDEM_GERAL,
            fill_value=0,
        )
        for nome_faixa in ORDEM_FAIXAS:
            for nome_geral in ORDEM_GERAL:
                n = int(cruzamento.loc[nome_faixa, nome_geral])
                total_geral = int(categoria_geral.eq(nome_geral).sum())
                linhas.append({
                    "metrica": metrica,
                    "faixa": nome_faixa,
                    "classificacao_geral": nome_geral,
                    "repositorios": n,
                    "percentual_na_categoria_geral": (
                        n / total_geral * 100 if total_geral else float("nan")
                    ),
                })
    return pd.DataFrame(linhas)


def grafico_empilhado(df: pd.DataFrame):
    """Plota a distribuição percentual das quatro faixas e da geral C1."""
    rotulos = {**NOTAS_DORA, "classificacao_geral": "Classificação geral C1"}
    cores = {
        "Low": "#C0504D",
        "Medium": "#F2C811",
        "High": "#70AD47",
        "Elite": "#4472C4",
        "Sem nota": "#BFBFBF",
    }
    total = len(df)
    fig, eixo = plt.subplots(figsize=(8.2, 4.2))
    esquerda = [0.0] * len(rotulos)
    for categoria in ORDEM_FAIXAS:
        valores = []
        for coluna in rotulos:
            if coluna == "classificacao_geral":
                notas = df[coluna].map(FAIXAS).fillna("Sem classificação")
                valores.append(float(notas.eq(categoria).sum()) / total * 100 if total else 0)
            else:
                notas = df[coluna].map(FAIXAS).fillna("Sem nota")
                valores.append(float(notas.eq(categoria).sum()) / total * 100 if total else 0)
        eixo.barh(
            [rotulos[coluna] for coluna in rotulos],
            valores,
            left=esquerda,
            color=cores[categoria],
            label=categoria,
        )
        esquerda = [atual + valor for atual, valor in zip(esquerda, valores)]

    sem_classificacao = (
        float(df["classificacao_geral"].isna().sum()) / total * 100 if total else 0
    )
    eixo.barh(
        ["Classificação geral C1"],
        [sem_classificacao],
        left=[esquerda[-1]],
        color=cores["Sem nota"],
        label="Sem classificação",
    )
    eixo.set_xlim(0, 100)
    eixo.set_xlabel("Repositórios (%)")
    eixo.set_title("Distribuição das faixas DORA e da classificação C1")
    eixo.legend(title="Faixa", ncols=3, loc="lower center", bbox_to_anchor=(0.5, -0.38))
    eixo.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    return fig


def main() -> int:
    df = carregar()
    tabela_dados = dados_c1(df)
    geral = distribuicao_geral(df)
    notas = contagem_notas(df)
    cruzada = tabela_cruzada(df)

    salvar_tabela(tabela_dados, "classificacao_c1")
    salvar_tabela(geral, "classificacao_c1_distribuicao")
    salvar_tabela(notas, "classificacao_c1_notas")
    salvar_tabela(cruzada, "classificacao_c1_cruzada")
    fig = grafico_empilhado(tabela_dados)
    salvar_figura(fig, "classificacao_c1")
    plt.close(fig)

    print("Classificação DORA de referência C1")
    print(geral.to_string(index=False))
    print("\nCobertura das notas")
    print(notas.to_string(index=False))
    print("\nTabelas cruzadas por métrica e classificação geral")
    print(cruzada.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

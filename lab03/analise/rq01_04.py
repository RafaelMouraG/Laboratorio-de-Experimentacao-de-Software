"""Análises descritivas das RQ 01 a RQ 04.

Execute da raiz do repositório com ``python -m lab03.analise.rq01_04``.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from lab03.analise.comum import carregar, resumo, salvar_figura, salvar_tabela

METRICAS = {
    "releases_por_semana": {
        "nome": "Releases por semana",
        "faixa": "faixa_releases",
        "variante": "Única",
        "unidade": "releases/semana",
    },
    "lead_time_release_horas": {
        "nome": "Lead time (a)",
        "faixa": "faixa_lead_time_release",
        "variante": "(a)",
        "unidade": "horas",
    },
    "lead_time_commit_horas": {
        "nome": "Lead time (b)",
        "faixa": "faixa_lead_time_commit",
        "variante": "(b)",
        "unidade": "horas",
    },
    "cfr_ci": {
        "nome": "CFR (a)",
        "faixa": "faixa_cfr_ci",
        "variante": "(a)",
        "unidade": "proporção",
    },
    "cfr_entrega": {
        "nome": "CFR (b)",
        "faixa": "faixa_cfr_entrega",
        "variante": "(b)",
        "unidade": "proporção",
    },
    "recuperacao_mediana_horas": {
        "nome": "Tempo de recuperação",
        "faixa": "faixa_recuperacao",
        "variante": "Única",
        "unidade": "horas",
    },
}

FAIXAS = {4: "Elite", 3: "High", 2: "Medium", 1: "Low"}


def tabela_resumos(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula n, ausentes, mediana, quartis e IQR de cada métrica."""
    linhas = []
    for coluna, metadados in METRICAS.items():
        linhas.append({
            "metrica": metadados["nome"],
            "unidade": metadados["unidade"],
            **resumo(df[coluna]),
        })
    return pd.DataFrame(linhas)


def distribuicao_faixas(df: pd.DataFrame) -> pd.DataFrame:
    """Conta repositórios em cada faixa DORA, mantendo categorias sem ocorrências."""
    linhas = []
    for metrica, metadados in METRICAS.items():
        faixas = df[metadados["faixa"]]
        n = int(faixas.notna().sum())
        ausentes = int(faixas.isna().sum())
        contagens = faixas.value_counts()
        for codigo, nome in FAIXAS.items():
            quantidade = int(contagens.get(codigo, 0))
            linhas.append({
                "metrica": metadados["nome"],
                "variante": metadados["variante"],
                "faixa": nome,
                "repositorios": quantidade,
                "percentual": quantidade / n * 100 if n else float("nan"),
                "n_ausentes": ausentes,
            })
    return pd.DataFrame(linhas)


def comparacao_lead_time(df: pd.DataFrame) -> pd.DataFrame:
    """Compara as variantes (a) e (b) e resume a razão entre elas."""
    a = df["lead_time_release_horas"]
    b = df["lead_time_commit_horas"]
    comparaveis = a.notna() & b.notna()
    razoes = a[comparaveis & b.gt(0)] / b[comparaveis & b.gt(0)]
    return pd.DataFrame([{
        "comparaveis": int(comparaveis.sum()),
        "a_maior_que_b": int((a[comparaveis] > b[comparaveis]).sum()),
        "mediana_razao_a_b": razoes.median(),
        "razao_com_b_zero": int((comparaveis & b.eq(0)).sum()),
        "ausentes_em_alguma_variante": int((~comparaveis).sum()),
    }])


def resumo_cfr_entrega(df: pd.DataFrame) -> pd.DataFrame:
    """Conta CFR (b) igual a zero e valores ausentes por censura."""
    sem_cfr_por_censura = (
        df["cfr_entrega"].isna()
        & df["cfr_entrega_avaliadas"].eq(0)
        & df["cfr_entrega_censuradas"].gt(0)
    )
    return pd.DataFrame([
        {
            "situacao": "CFR (b) igual a zero",
            "repositorios": int(df["cfr_entrega"].eq(0).sum()),
        },
        {
            "situacao": "Sem CFR (b) por censura",
            "repositorios": int(sem_cfr_por_censura.sum()),
        },
    ])


def resumo_censura(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Resume a proporção de episódios censurados e conta repositórios sem episódios."""
    proporcao = resumo(df["recuperacao_proporcao_censurados"])
    tabela = pd.DataFrame([{
        "metrica": "Proporção de episódios censurados",
        **proporcao,
    }])
    sem_episodios = int(df["recuperacao_episodios"].eq(0).sum())
    return tabela, sem_episodios


def grafico_rq01(df: pd.DataFrame):
    valores = df["releases_por_semana"].dropna()
    fig, eixo = plt.subplots(figsize=(6.2, 3.8))
    positivos = valores[valores > 0]
    if not positivos.empty:
        bins = np.logspace(np.log10(positivos.min()), np.log10(positivos.max()), 25)
        eixo.hist(positivos, bins=bins, color="#4472C4", edgecolor="white")
        eixo.set_xscale("log")
    eixo.set_title("RQ 01: distribuição de releases por semana")
    eixo.set_xlabel("Releases por semana (escala log)")
    eixo.set_ylabel("Repositórios")
    fig.tight_layout()
    return fig


def grafico_rq02(df: pd.DataFrame):
    fig, eixo = plt.subplots(figsize=(5.6, 3.8))
    colunas = ["lead_time_release_horas", "lead_time_commit_horas"]
    valores = [df[coluna].dropna() for coluna in colunas]
    eixo.boxplot(valores, tick_labels=["(a) Por release", "(b) Por commit"])
    eixo.set_yscale("log")
    eixo.set_title("RQ 02: lead time por variante")
    eixo.set_ylabel("Horas (escala log)")
    fig.tight_layout()
    return fig


def grafico_rq03(df: pd.DataFrame):
    fig, eixo = plt.subplots(figsize=(5.6, 3.8))
    colunas = ["cfr_ci", "cfr_entrega"]
    valores = [df[coluna].dropna() for coluna in colunas]
    eixo.boxplot(valores, tick_labels=["(a) CI", "(b) Entrega"])
    eixo.set_title("RQ 03: distribuição da CFR por variante")
    eixo.set_ylabel("CFR")
    eixo.set_ylim(-0.03, 1.03)
    fig.tight_layout()
    return fig


def grafico_rq04(df: pd.DataFrame):
    valores = df["recuperacao_proporcao_censurados"].dropna()
    fig, eixo = plt.subplots(figsize=(4.8, 3.8))
    eixo.boxplot([valores], tick_labels=["Episódios censurados"])
    eixo.set_title("RQ 04: proporção de episódios censurados")
    eixo.set_ylabel("Proporção")
    eixo.set_ylim(-0.03, 1.03)
    fig.tight_layout()
    return fig


def main() -> int:
    df = carregar()
    resumos = tabela_resumos(df)
    faixas = distribuicao_faixas(df)
    lead_time = comparacao_lead_time(df)
    cfr = resumo_cfr_entrega(df)
    censura, sem_episodios = resumo_censura(df)

    salvar_tabela(resumos, "rq01_04_resumos")
    salvar_tabela(faixas, "rq01_04_faixas")
    salvar_tabela(lead_time, "rq02_comparacao")
    salvar_tabela(cfr, "rq03_cfr_entrega")
    salvar_tabela(censura, "rq04_censura")

    for nome, gerar in (
        ("rq01_frequencia", grafico_rq01),
        ("rq02_lead_time", grafico_rq02),
        ("rq03_cfr", grafico_rq03),
        ("rq04_censura", grafico_rq04),
    ):
        fig = gerar(df)
        salvar_figura(fig, nome)
        plt.close(fig)

    print("RQ 01–04: resumo descritivo")
    print(resumos.to_string(index=False))
    print("\nDistribuição das faixas DORA")
    print(faixas.to_string(index=False))
    print("\nRQ 02: comparação do lead time")
    print(lead_time.to_string(index=False))
    print("\nRQ 03: CFR (b)")
    print(cfr.to_string(index=False))
    print("\nRQ 04: censura")
    print(censura.to_string(index=False))
    print(f"Repositórios sem episódios de recuperação: {sem_episodios}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

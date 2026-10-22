"""RQ 06: características dos repositórios × desempenho DORA.

Execute da raiz do repositório com ``python -m lab03.analise.rq06``.
"""

from __future__ import annotations

import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from statsmodels.stats.multitest import multipletests

from lab03.analise.comum import DADOS, carregar, salvar_figura, salvar_tabela
from lab03.analise.estatistica import cliffs_delta, comparar_grupos, magnitude

ALFA = 0.05
QUARTIS = ("Q1", "Q2", "Q3", "Q4")
# Linguagens com menos repositórios que isso vão para "Outras": com 10 por grupo
# a aproximação qui-quadrado do Kruskal-Wallis já é segura e sobram 7 linguagens.
MIN_REPOS_LINGUAGEM = 10
OUTRAS = "Outras"
# Na amostra-ouro, tipos com menos repositórios que isso ficam fora do teste.
MIN_REPOS_TIPO = 5

METRICAS = {
    "releases_por_semana": "Releases por semana",
    "lead_time_release_horas": "Lead time (a), horas",
    "cfr_ci": "CFR (a)",
    "recuperacao_mediana_horas": "Recuperação, horas",
}
ESCALA_LOG = frozenset(("releases_por_semana", "lead_time_release_horas", "recuperacao_mediana_horas"))
QUANTITATIVOS = {
    "quartil_estrelas": "estrelas",
    "quartil_contribuidores": "contribuidores",
    "quartil_idade": "idade_anos",
}
FATORES = (*QUANTITATIVOS, "grupo_linguagem")
NOMES_FATORES = {
    "quartil_estrelas": "Estrelas",
    "quartil_contribuidores": "Contribuidores",
    "quartil_idade": "Idade",
    "grupo_linguagem": "Linguagem",
    "tipo_projeto": "Tipo de projeto",
}


def agrupar_linguagens(linguagens: pd.Series, minimo: int = MIN_REPOS_LINGUAGEM) -> pd.Series:
    """Junta em ``Outras`` as linguagens com menos de ``minimo`` repositórios."""
    contagem = linguagens.value_counts()
    raras = contagem[contagem < minimo].index
    return linguagens.where(~linguagens.isin(raras), OUTRAS)


def preparar_fatores(df: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta os quartis de estrelas, contribuidores e idade e o grupo de linguagem."""
    df = df.copy()
    for fator, coluna in QUANTITATIVOS.items():
        df[fator] = pd.qcut(df[coluna], 4, labels=QUARTIS)
    df["grupo_linguagem"] = agrupar_linguagens(df["linguagem"])
    return df


def cortes_quartis(df: pd.DataFrame) -> pd.DataFrame:
    """Limites e tamanho de cada quartil, para mostrar o efeito dos empates."""
    linhas = []
    for fator, coluna in QUANTITATIVOS.items():
        for quartil, grupo in df.groupby(fator, observed=True)[coluna]:
            linhas.append({
                "fator": fator,
                "grupo": quartil,
                "minimo": grupo.min(),
                "maximo": grupo.max(),
                "n": len(grupo),
            })
    return pd.DataFrame(linhas)


def testar(df: pd.DataFrame, fatores=FATORES, metricas=METRICAS) -> pd.DataFrame:
    """Roda um teste por fator × métrica e aplica Holm sobre todos eles juntos."""
    tabela = pd.DataFrame([comparar_grupos(df, fator, metrica) for fator in fatores for metrica in metricas])
    rejeita, p_ajustado, _, _ = multipletests(tabela["p_valor"], alpha=ALFA, method="holm")
    tabela["p_ajustado"] = p_ajustado
    tabela["significativo"] = rejeita
    return tabela


def extremos(df: pd.DataFrame, fator: str, metrica: str) -> tuple[str, str]:
    """Grupos comparados pelo delta: Q4 × Q1 ou maior × menor mediana entre as linguagens."""
    if fator in QUANTITATIVOS:
        return QUARTIS[-1], QUARTIS[0]
    medianas = df[df[fator] != OUTRAS].groupby(fator, observed=True)[metrica].median().dropna()
    return medianas.idxmax(), medianas.idxmin()


def direcoes(df: pd.DataFrame, testes: pd.DataFrame) -> pd.DataFrame:
    """Delta de Cliff entre os grupos extremos das combinações significativas."""
    linhas = []
    for linha in testes[testes["significativo"]].itertuples():
        grupo_a, grupo_b = extremos(df, linha.fator, linha.metrica)
        x = df.loc[df[linha.fator] == grupo_a, linha.metrica].dropna()
        y = df.loc[df[linha.fator] == grupo_b, linha.metrica].dropna()
        delta = cliffs_delta(x, y)
        linhas.append({
            "fator": linha.fator,
            "metrica": linha.metrica,
            "grupo_a": grupo_a,
            "mediana_a": x.median(),
            "n_a": len(x),
            "grupo_b": grupo_b,
            "mediana_b": y.median(),
            "n_b": len(y),
            "delta_cliff": delta,
            "magnitude": magnitude(delta),
        })
    return pd.DataFrame(linhas, columns=[
        "fator", "metrica", "grupo_a", "mediana_a", "n_a",
        "grupo_b", "mediana_b", "n_b", "delta_cliff", "magnitude",
    ])


def tipo_projeto(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Análise à parte nos 60 repositórios da amostra-ouro, com Holm próprio."""
    consenso = pd.read_csv(DADOS.parent / "validacao" / "consenso_repos.csv")
    ouro = df.merge(consenso[["repo", "consenso_tipo_projeto"]], on="repo", how="inner")
    ouro = ouro.rename(columns={"consenso_tipo_projeto": "tipo_projeto"})
    tamanhos = ouro["tipo_projeto"].value_counts()
    ouro = ouro[ouro["tipo_projeto"].isin(tamanhos[tamanhos >= MIN_REPOS_TIPO].index)]
    return testar(ouro, fatores=("tipo_projeto",)), tamanhos


def boxplots(df: pd.DataFrame, testes: pd.DataFrame):
    """Um boxplot por combinação significativa; ``None`` se não houver nenhuma."""
    significativos = testes[testes["significativo"]]
    if significativos.empty:
        return None
    colunas = min(3, len(significativos))
    linhas = math.ceil(len(significativos) / colunas)
    fig, eixos = plt.subplots(linhas, colunas, figsize=(4.2 * colunas, 3.4 * linhas), squeeze=False)
    for eixo, linha in zip(eixos.flat, significativos.itertuples()):
        grupos = [nome for nome in df[linha.fator].dropna().unique()]
        grupos = sorted(grupos, key=str) if linha.fator in QUANTITATIVOS else sorted(
            grupos, key=lambda nome: (nome == OUTRAS, nome)
        )
        valores = [df.loc[df[linha.fator] == nome, linha.metrica].dropna() for nome in grupos]
        eixo.boxplot(valores, tick_labels=grupos)
        if linha.metrica in ESCALA_LOG:
            eixo.set_yscale("log")
        eixo.set_title(f"{NOMES_FATORES[linha.fator]} (p aj. = {linha.p_ajustado:.3g})", fontsize=9)
        eixo.set_ylabel(METRICAS[linha.metrica], fontsize=8)
        eixo.tick_params(axis="x", labelrotation=45 if linha.fator == "grupo_linguagem" else 0, labelsize=8)
    for eixo in list(eixos.flat)[len(significativos):]:
        eixo.set_visible(False)
    fig.tight_layout()
    return fig


def main() -> int:
    df = preparar_fatores(carregar())
    testes = testar(df)
    sentidos = direcoes(df, testes)
    testes_tipo, tamanhos_tipo = tipo_projeto(df)

    salvar_tabela(cortes_quartis(df), "rq06_quartis")
    salvar_tabela(df["grupo_linguagem"].value_counts().rename_axis("linguagem").reset_index(), "rq06_linguagens")
    salvar_tabela(testes, "rq06_testes")
    salvar_tabela(sentidos, "rq06_direcoes")
    salvar_tabela(testes_tipo, "rq06_tipo_projeto")
    fig = boxplots(df, testes)
    if fig is not None:
        salvar_figura(fig, "rq06_boxplots")
        plt.close(fig)

    colunas = ["fator", "metrica", "teste", "n", "estatistica", "p_valor", "p_ajustado", "efeito"]
    print(f"RQ 06: {len(testes)} testes, {int(testes['significativo'].sum())} significativos após Holm")
    print(testes[colunas].to_string(index=False))
    if not sentidos.empty:
        print(sentidos.to_string(index=False))
    print(f"Tipo de projeto (n por tipo: {tamanhos_tipo.to_dict()}):")
    print(testes_tipo[colunas].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""RQ 08: deployment rework rate e comparação com a CFR (b).

Execute da raiz do repositório com ``python -m lab03.analise.rq08``.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from lab03.analise.comum import DADOS, FIGURAS, resumo, salvar_figura, salvar_tabela
from lab03.analise.rq05 import correlacao
from lab03.metricas.corretiva import eh_corretiva

COLUNA_REWORK = "rework_rate"
COLUNA_CFR = "cfr_entrega"
TOP_DIVERGENCIAS = 10


def _booleano(valor) -> bool:
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, str):
        normalizado = valor.strip().lower()
        if normalizado in {"true", "1", "sim"}:
            return True
        if normalizado in {"false", "0", "nao", "não", ""}:
            return False
    if pd.isna(valor):
        return False
    return bool(valor)


def _release_corretiva(release: dict) -> bool:
    if "eh_corretiva" in release:
        return _booleano(release["eh_corretiva"])
    return eh_corretiva(release)


def rework_rate(releases: Iterable[dict]) -> float | None:
    """Corretivas divididas pelas releases da janela que têm uma anterior."""
    avaliaveis = [release for release in releases if not _booleano(release.get("sem_anterior", False))]
    if not avaliaveis:
        return None
    corretivas = sum(_release_corretiva(release) for release in avaliaveis)
    return corretivas / len(avaliaveis)


def carregar_releases(caminho: Path = DADOS / "releases.csv") -> pd.DataFrame:
    """Lê releases com a decisão v4 persistida durante a coleta."""
    releases = pd.read_csv(caminho)
    if "eh_corretiva" not in releases:
        raise ValueError(
            f"{caminho} não tem a coluna eh_corretiva. Gere novamente os CSVs a partir do cache "
            "com `python -m lab03.pipeline --config lab03/config.yaml --parcial`."
        )
    releases["eh_corretiva"] = releases["eh_corretiva"].map(_booleano)
    releases["sem_anterior"] = releases["sem_anterior"].map(_booleano)
    return releases


def taxas_por_repositorio(releases: pd.DataFrame) -> pd.DataFrame:
    """Calcula numerador, denominador e rework rate de cada repositório."""
    avaliaveis = releases[~releases["sem_anterior"]].copy()
    tabela = (
        avaliaveis.groupby("repo", as_index=False)
        .agg(releases_avaliaveis=("repo", "size"), releases_corretivas=("eh_corretiva", "sum"))
    )
    tabela[COLUNA_REWORK] = tabela["releases_corretivas"] / tabela["releases_avaliaveis"]
    return tabela


def juntar_cfr(taxas: pd.DataFrame, metricas: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta a CFR (b) e a divergência absoluta entre as métricas."""
    colunas = ["repo", COLUNA_CFR, "cfr_entrega_avaliadas", "cfr_entrega_censuradas"]
    tabela = taxas.merge(metricas[colunas], on="repo", how="left", validate="one_to_one")
    tabela["diferenca_rework_cfr"] = tabela[COLUNA_REWORK] - tabela[COLUNA_CFR]
    tabela["divergencia_absoluta"] = tabela["diferenca_rework_cfr"].abs()
    return tabela


def resumo_rework(tabela: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame([{"metrica": "Rework rate", **resumo(tabela[COLUNA_REWORK])}])


def maiores_divergencias(tabela: pd.DataFrame, limite: int = TOP_DIVERGENCIAS) -> pd.DataFrame:
    """Repositórios com maior distância absoluta entre rework rate e CFR (b)."""
    colunas = [
        "repo",
        "releases_avaliaveis",
        "releases_corretivas",
        COLUNA_REWORK,
        COLUNA_CFR,
        "cfr_entrega_avaliadas",
        "cfr_entrega_censuradas",
        "diferenca_rework_cfr",
        "divergencia_absoluta",
    ]
    return tabela.dropna(subset=[COLUNA_CFR]).nlargest(limite, "divergencia_absoluta")[colunas]


def dispersao(tabela: pd.DataFrame, resultado: dict):
    validos = tabela[[COLUNA_REWORK, COLUNA_CFR]].dropna()
    fig, eixo = plt.subplots(figsize=(5.2, 4.2))
    eixo.scatter(validos[COLUNA_REWORK], validos[COLUNA_CFR], s=12, alpha=0.55)
    eixo.plot([0, 1], [0, 1], color="#777777", linestyle="--", linewidth=1)
    eixo.set_xlim(-0.03, 1.03)
    eixo.set_ylim(-0.03, 1.03)
    eixo.set_xlabel("Rework rate")
    eixo.set_ylabel("CFR (b)")
    eixo.set_title(
        f"RQ 08: rework rate × CFR (b)\n"
        f"ρ = {resultado['rho']:.2f}, p = {resultado['p_valor']:.3g}, n = {resultado['n']}"
    )
    fig.tight_layout()
    return fig


def main() -> int:
    releases = carregar_releases()
    metricas = pd.read_csv(DADOS / "metricas.csv")
    tabela = juntar_cfr(taxas_por_repositorio(releases), metricas)
    resumo_tabela = resumo_rework(tabela)
    resultado = correlacao(tabela, COLUNA_REWORK, COLUNA_CFR)
    correlacao_tabela = pd.DataFrame([resultado])
    divergencias = maiores_divergencias(tabela)

    salvar_tabela(tabela, "rq08_rework_por_repo")
    salvar_tabela(resumo_tabela, "rq08_resumo")
    salvar_tabela(correlacao_tabela, "rq08_correlacao")
    salvar_tabela(divergencias, "rq08_divergencias")
    fig = dispersao(tabela, resultado)
    salvar_figura(fig, "rq08_dispersao")
    fig.savefig(FIGURAS / "rq08_dispersao.png", bbox_inches="tight", dpi=160)
    plt.close(fig)

    print("RQ 08: deployment rework rate")
    print(resumo_tabela.to_string(index=False))
    print("\nSpearman entre rework rate e CFR (b)")
    print(correlacao_tabela.to_string(index=False))
    print("\nMaiores divergências")
    print(divergencias.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

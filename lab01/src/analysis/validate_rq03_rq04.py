"""Validação de RQ03 (releases) e RQ04 (dias desde o último push) nos 1.000 repositórios.

Não é análise: é a conferência de consistência da coleta que a Lab01S02 pede por integrante
(distribuição, outliers, valores ausentes) antes de a métrica ir para o relatório. Reaproveita o
`juntar` de `analyze_rq03.py` para que `releases_por_ano` e `sem_release` sejam calculados aqui
exatamente como na análise — se as duas divergissem, o percentual reportado na issue não bateria
com o CSV de resumo.
"""

import argparse
import os

import pandas as pd

from analyze_rq03 import carregar, juntar

RELEASES_CAP = 1000

FAIXAS_PUSH = [1, 7, 30, 90, 180, 365, 730]


def distribuicao(serie: pd.Series, rotulo: str) -> dict:
    return {
        "metrica": rotulo,
        "repos": len(serie),
        "min": round(serie.min(), 2),
        "q1": round(serie.quantile(0.25), 2),
        "mediana": round(serie.median(), 2),
        "q3": round(serie.quantile(0.75), 2),
        "p90": round(serie.quantile(0.90), 2),
        "max": round(serie.max(), 2),
        "media": round(serie.mean(), 2),
    }


def outliers_iqr(serie: pd.Series) -> tuple[float, int]:
    """Limite superior de Tukey e quantos repositórios ficam acima dele."""
    q1, q3 = serie.quantile([0.25, 0.75])
    limite = q3 + 1.5 * (q3 - q1)
    return round(limite, 2), int((serie > limite).sum())


def ausentes(caminho: str, colunas: list[str]) -> pd.DataFrame:
    """Célula vazia, valor não numérico e valor negativo — os três jeitos de o dado faltar aqui.

    Lê de novo com `keep_default_na=False` e sem conversão para enxergar a string crua: depois de
    `read_csv` converter a coluna, um campo vazio já viraria NaN e um lixo textual quebraria a
    leitura, então a contagem seria feita em cima de um dado que o pandas já mexeu.
    """
    bruto = carregar(caminho, ["repo"] + colunas)
    linhas = []
    for coluna in colunas:
        texto = bruto[coluna].astype(str).str.strip()
        numero = pd.to_numeric(texto, errors="coerce")
        linhas.append(
            {
                "coluna": coluna,
                "vazios": int((texto == "").sum()),
                "nao_numericos": int(numero.isna().sum() - (texto == "").sum()),
                "negativos": int((numero < 0).sum()),
            }
        )
    return pd.DataFrame(linhas)


def faixas_de_push(serie: pd.Series) -> pd.DataFrame:
    linhas = [
        {
            "ultimo_push_ate": f"{limite} dia(s)",
            "repos": int((serie <= limite).sum()),
            "percentual": round(100 * (serie <= limite).mean(), 1),
        }
        for limite in FAIXAS_PUSH
    ]
    linhas.append(
        {
            "ultimo_push_ate": "mais de 730 dias",
            "repos": int((serie > FAIXAS_PUSH[-1]).sum()),
            "percentual": round(100 * (serie > FAIXAS_PUSH[-1]).mean(), 1),
        }
    )
    return pd.DataFrame(linhas)


def push_vs_update(df: pd.DataFrame) -> None:
    """Por que a RQ04 usa `pushedAt` e não `updatedAt`, medido no próprio CSV.

    `updatedAt` muda com star, label e edição de descrição — coisas sem relação com
    desenvolvimento. A comparação abaixo mostra o tamanho do erro que a troca causaria.
    """
    push = df["days_since_last_push"]
    update = df["days_since_last_update"]
    diferenca = push - update
    print(
        f"mediana de dias desde o último push: {round(push.median(), 2)} | "
        f"desde o último updatedAt: {round(update.median(), 2)}"
    )
    print(
        f"{int((update < push).sum())} dos {len(df)} repositórios têm updatedAt mais recente que "
        f"pushedAt; {int((diferenca > 30).sum())} divergem em mais de 30 dias e "
        f"{int((diferenca > 365).sum())} em mais de um ano (máx. {round(diferenca.max(), 2)} dias)."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", default="lab01/data/sprint_s02/all_rqs.csv")
    parser.add_argument("--comparar", default="lab01/data/sprint_s01/all_rqs.csv")
    parser.add_argument("--out", default="lab01/data/sprint_s02/rq04_faixas_push.csv")
    parser.add_argument("--listar", type=int, default=10)
    args = parser.parse_args()

    df = juntar(args.entrada)
    push = carregar(args.entrada, ["repo", "days_since_last_push", "days_since_last_update"])
    df = df.merge(push, on="repo")

    print(f"{len(df)} linhas, {df['repo'].nunique()} repositórios distintos em {args.entrada}")

    print("\n[1] Valores ausentes")
    colunas = ["releases", "age_years", "days_since_last_push", "days_since_last_update"]
    print(ausentes(args.entrada, colunas).to_string(index=False))

    print("\n[2] Distribuição")
    com_release = df[~df["sem_release"]]
    linhas = [
        distribuicao(df["releases"], "releases (todos)"),
        distribuicao(com_release["releases"], "releases (só com release)"),
        distribuicao(df["releases_por_ano"], "releases_por_ano (todos)"),
        distribuicao(com_release["releases_por_ano"], "releases_por_ano (só com release)"),
        distribuicao(df["days_since_last_push"], "days_since_last_push"),
    ]
    print(pd.DataFrame(linhas).to_string(index=False))

    print("\n[3] Outliers (limite superior de Tukey: Q3 + 1,5 x IQR)")
    for metrica in ["releases", "releases_por_ano", "days_since_last_push"]:
        limite, acima = outliers_iqr(df[metrica])
        print(f"  {metrica:22s} limite {limite:>10} | {acima} repositórios acima")
    print(
        "  Cauda longa é esperada nas três: a lista mistura projeto de release diária com "
        "repositório de conteúdo parado há anos. Outlier aqui é dado real, não erro de coleta."
    )

    print("\n[4] RQ03 - repositórios sem nenhuma release")
    sem_release = df[df["sem_release"]]
    print(
        f"  {len(sem_release)} de {len(df)} "
        f"({round(100 * len(sem_release) / len(df), 1)}%) em {args.entrada}"
    )
    try:
        anterior = juntar(args.comparar)
    except SystemExit:
        anterior = None
    if anterior is not None:
        zerados = int(anterior["sem_release"].sum())
        print(
            f"  {zerados} de {len(anterior)} "
            f"({round(100 * zerados / len(anterior), 1)}%) em {args.comparar}"
        )
        print(
            "  O recorte é sensível ao corte de popularidade: quanto mais alto o corte, maior a "
            "concentração de repositório de conteúdo (lista, livro, roadmap), que não publica "
            "release. O relatório precisa citar o percentual junto com o tamanho da amostra."
        )

    print(f"\n[5] RQ03 - {args.listar} repositórios sem release com mais estrelas")
    colunas = ["repo", "primary_language", "stars", "age_years"]
    print(sem_release.nlargest(args.listar, "stars")[colunas].to_string(index=False))

    print(f"\n[6] RQ03 - sentinela do orderBy (releases == {RELEASES_CAP})")
    truncados = df[df["releases"] == RELEASES_CAP]
    acima_do_cap = int((df["releases"] > RELEASES_CAP).sum())
    if len(truncados):
        print(
            f"  ATENÇÃO: {len(truncados)} repositório(s) com exatamente {RELEASES_CAP} releases — "
            "sintoma de orderBy ausente na query (ver limitação 1 do README):"
        )
        print(truncados[["repo", "releases"]].to_string(index=False))
    else:
        print(
            f"  Nenhum repositório com exatamente {RELEASES_CAP} releases. "
            f"{acima_do_cap} passam de {RELEASES_CAP} (máx. {int(df['releases'].max())}), "
            "então o totalCount não está truncado."
        )

    print("\n[7] RQ04 - quando foi o último push (faixas acumuladas)")
    faixas = faixas_de_push(df["days_since_last_push"])
    print(faixas.to_string(index=False))

    print(f"\n[8] RQ04 - {args.listar} repositórios parados há mais tempo")
    colunas = ["repo", "primary_language", "stars", "days_since_last_push"]
    print(df.nlargest(args.listar, "days_since_last_push")[colunas].to_string(index=False))

    print("\n[9] RQ04 - pushedAt vs. updatedAt")
    push_vs_update(df)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    faixas.to_csv(args.out, index=False)
    print(
        f"\nFaixas da RQ04 salvas em {args.out}. É o único CSV derivado da RQ04: as saídas do "
        "analyze_rq03.py trazem só as colunas de release, e days_since_last_push fica no all_rqs.csv."
    )


if __name__ == "__main__":
    main()

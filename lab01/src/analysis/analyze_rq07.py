"""RQ07: RQ02, RQ03 e RQ04 divididas por linguagem primária (RQ05)"""

import argparse
import os

import pandas as pd

from viz_common import carregar_dados

TOP_LANGUAGES = [
    "Python",
    "C",
    "C++",
    "Java",
    "C#",
    "JavaScript",
    "Visual Basic",
    "SQL",
    "R",
    "Rust",
]

SEM_LINGUAGEM = "N/A"

GRUPO_TOP = "top-10 TIOBE"
GRUPO_DEMAIS = "demais linguagens"
GRUPO_NENHUMA = "sem linguagem primária"


def juntar(entrada: str) -> pd.DataFrame:
    df = carregar_dados(
        entrada,
        [
            "repo",
            "primary_language",
            "merged_pull_requests",
            "releases",
            "days_since_last_push",
            "age_years",
        ],
    )
    return df.assign(
        releases_por_ano=(df["releases"] / df["age_years"]).round(2),
        grupo=df["primary_language"].map(classificar),
    )


def classificar(linguagem: str) -> str:
    if linguagem == SEM_LINGUAGEM:
        return GRUPO_NENHUMA
    return GRUPO_TOP if linguagem in TOP_LANGUAGES else GRUPO_DEMAIS


def agregar(df: pd.DataFrame, chave: str) -> pd.DataFrame:
    """Medianas das três métricas da RQ07 (RQ02, RQ03 e RQ04) por `chave`.

    `mediana_releases_por_ano` é a métrica de release principal, pelo mesmo motivo da RQ03: o total
    bruto acumulado mede tempo de vida e favorece repositório antigo. Aqui isso pesa mais ainda,
    porque a RQ07 compara grupos de idades diferentes (Ruby tem idade mediana de 12,11 anos contra
    3,93 de Python) — sem normalizar, a comparação por linguagem mediria idade junto com cadência.
    `mediana_releases` fica como métrica secundária e `mediana_idade_anos` entra para deixar a
    diferença de idade entre os grupos visível na própria tabela.
    """
    tabela = df.groupby(chave).agg(
        repos=("repo", "count"),
        mediana_prs_aceitas=("merged_pull_requests", "median"),
        mediana_releases_por_ano=("releases_por_ano", "median"),
        mediana_releases=("releases", "median"),
        mediana_dias_sem_push=("days_since_last_push", "median"),
        mediana_idade_anos=("age_years", "median"),
    )
    # Duas casas nas colunas novas, a mesma precisão que `releases_por_ano` e `age_years` já têm por
    # repositório: a mediana de um par de valores cai no meio e traz ruído de ponto flutuante
    # (6,505000000000001 no grupo top-10 TIOBE). As colunas antigas ficam sem arredondar para não
    # mexer nos CSVs da S01.
    return tabela.round({"mediana_releases_por_ano": 2, "mediana_idade_anos": 2})


def por_linguagem(df: pd.DataFrame, min_repos: int = 0) -> pd.DataFrame:
    """Medianas por linguagem primária, opcionalmente cortando a cauda de linguagens raras.

    Com `min_repos=0` (padrão) devolve todas as linguagens. Com `min_repos > 0` mantém só as que
    têm massa crítica — mesmo padrão do `sem_release_por_linguagem` da RQ03. É a limitação 5 do
    README: nos 1.000, 11 linguagens aparecem com um único repositório, e ali a "mediana" é o
    próprio repositório. Com `min_repos=10` sobram 14 linguagens, que cobrem 913 dos 1.000.
    """
    tabela = agregar(df, "primary_language")
    if min_repos:
        tabela = tabela[tabela["repos"] >= min_repos]
    tabela.insert(0, "grupo", [classificar(linguagem) for linguagem in tabela.index])
    return tabela.sort_values(["repos", "mediana_prs_aceitas"], ascending=False)


def por_grupo(df: pd.DataFrame) -> pd.DataFrame:
    ordem = [GRUPO_TOP, GRUPO_DEMAIS, GRUPO_NENHUMA]
    tabela = agregar(df, "grupo")
    return tabela.reindex([grupo for grupo in ordem if grupo in tabela.index])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", default="lab01/data/sprint_s01/all_rqs.csv")
    parser.add_argument("--out", default="lab01/data/sprint_s01/rq07_por_linguagem.csv")
    parser.add_argument("--out-grupos", default="lab01/data/sprint_s01/rq07_top_vs_demais.csv")
    parser.add_argument(
        "--min-repos",
        type=int,
        default=0,
        help="corte mínimo de repositórios na tabela por linguagem (0 = sem corte)",
    )
    args = parser.parse_args()

    df = juntar(args.entrada)
    print(f"{len(df)} repositórios cruzados, {df['primary_language'].nunique()} linguagens distintas")
    print(f"Linguagens mais populares (TIOBE Index 2026): {', '.join(TOP_LANGUAGES)}")

    tabela_linguagem = por_linguagem(df, args.min_repos)
    tabela_grupo = por_grupo(df)

    if args.min_repos:
        print(
            f"\nCorte de {args.min_repos} repositórios: {len(tabela_linguagem)} de "
            f"{df['primary_language'].nunique()} linguagens ficam na tabela, cobrindo "
            f"{int(tabela_linguagem['repos'].sum())} dos {len(df)} repositórios."
        )

    print("\nRQ07 - medianas por linguagem primária:")
    print(tabela_linguagem.to_string())

    print("\nRQ07 - linguagens mais populares vs. demais:")
    print(tabela_grupo.to_string())

    ausentes = [lang for lang in TOP_LANGUAGES if lang not in set(df["primary_language"])]
    if ausentes:
        print(
            f"\nDo top-10 TIOBE, {len(ausentes)} linguagens não aparecem em nenhum repositório da "
            f"amostra: {', '.join(ausentes)}. O TIOBE mede uso na indústria (incluindo código "
            "fechado) e o recorte aqui é dos repositórios open-source mais estrelados — as duas "
            "populações não são a mesma."
        )

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    tabela_linguagem.to_csv(args.out)
    tabela_grupo.to_csv(args.out_grupos)
    print(f"\nSalvo em {args.out} e {args.out_grupos}")
    print(
        "Lembre que a mediana de linguagens com poucos repositórios (coluna repos) diz pouco: "
        "leia a tabela por grupo para responder a RQ07."
    )


if __name__ == "__main__":
    main()

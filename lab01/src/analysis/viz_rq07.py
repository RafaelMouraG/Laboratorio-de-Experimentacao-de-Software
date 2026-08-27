"""RQ07: linguagens mais populares recebem mais contribuição, releases e atualizações? — não.

Lê as duas tabelas agregadas pelo `analyze_rq07.py` (`rq07_top_vs_demais.csv` e
`rq07_por_linguagem.csv`) e monta os dois gráficos que respondem a pergunta:

1. **Por grupo**, as três métricas (RQ02, RQ03 e RQ04) em painéis separados. Um eixo só não serve:
   PRs aceitas estão na casa do milhar, releases por ano na dezena e dias sem push na unidade.
2. **Por linguagem**, com o corte de 10 repositórios do `--min-repos`, colorindo cada barra pelo
   grupo — é o gráfico que mostra os grupos se intercalando em vez de se separarem, que é o motivo
   da resposta ser negativa.

Duas convenções valem nos dois gráficos: `days_since_last_push` tem sentido invertido em relação às
outras duas métricas (barra menor é melhor) e isso vai escrito no eixo, senão o leitor lê o painel
ao contrário; e o grupo "sem linguagem primária" aparece sempre separado, nunca somado às "demais"
(mesma convenção da RQ03 e da RQ05).
"""

import argparse
import textwrap

import matplotlib.pyplot as plt
import pandas as pd

from analyze_rq07 import GRUPO_DEMAIS, GRUPO_NENHUMA, GRUPO_TOP
from viz_common import carregar_dados, salvar, setup_estilo

COLUNAS_GRUPO = [
    "grupo",
    "repos",
    "mediana_prs_aceitas",
    "mediana_releases_por_ano",
    "mediana_dias_sem_push",
    "mediana_idade_anos",
]
COLUNAS_LINGUAGEM = ["primary_language"] + COLUNAS_GRUPO

# Mesmas cores do viz_rq05, para o leitor reconhecer os três grupos entre os gráficos das duas RQs.
CORES = {GRUPO_TOP: "#4C72B0", GRUPO_DEMAIS: "#A8B2C4", GRUPO_NENHUMA: "grey"}
HATCHES = {GRUPO_TOP: "", GRUPO_DEMAIS: "", GRUPO_NENHUMA: "//"}

# (coluna, título do painel, rótulo do eixo, escala log?). O "maior/menor é melhor" fica no rótulo
# do eixo porque é o que impede a leitura invertida do painel de dias sem push.
METRICAS = [
    (
        "mediana_prs_aceitas",
        "RQ02 - contribuição externa",
        "mediana de PRs aceitas (maior é melhor)",
        False,
    ),
    (
        "mediana_releases_por_ano",
        "RQ03 - frequência de release",
        "mediana de releases por ano (maior é melhor)",
        False,
    ),
    (
        "mediana_dias_sem_push",
        "RQ04 - atualização",
        "mediana de dias sem push, log (MENOR é melhor)",
        True,
    ),
]

MIN_REPOS_LINGUAGEM = 10


def formatar(valor: float) -> str:
    """Número no padrão do relatório: ponto como separador de milhar, vírgula decimal, sem
    zeros à direita (1076.0 vira "1.076"; 6.51 vira "6,51")."""
    texto = f"{valor:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return texto.rstrip("0").rstrip(",")


def cores_e_hatches(grupos: "pd.Series") -> tuple[list[str], list[str]]:
    return [CORES[grupo] for grupo in grupos], [HATCHES[grupo] for grupo in grupos]


def legenda(fig: plt.Figure) -> None:
    patches = [
        plt.Rectangle((0, 0), 1, 1, color=CORES[grupo], hatch=HATCHES[grupo])
        for grupo in (GRUPO_TOP, GRUPO_DEMAIS, GRUPO_NENHUMA)
    ]
    fig.legend(
        patches,
        [GRUPO_TOP, GRUPO_DEMAIS, GRUPO_NENHUMA],
        loc="lower center",
        ncol=3,
        bbox_to_anchor=(0.5, -0.02),
    )


def grafico_grupos(tabela: pd.DataFrame, nome: str) -> str:
    """Três painéis, um por métrica, com os três grupos lado a lado em cada um."""
    rotulos = [
        f"{textwrap.fill(grupo, 13)}\n({int(repos)} repos)"
        for grupo, repos in zip(tabela["grupo"], tabela["repos"])
    ]
    cores, hatches = cores_e_hatches(tabela["grupo"])

    fig, axes = plt.subplots(1, 3, figsize=(13, 5))
    for ax, (coluna, titulo, rotulo_eixo, usar_log) in zip(axes, METRICAS):
        valores = tabela[coluna]
        barras = ax.bar(rotulos, valores, color=cores, hatch=hatches)
        ax.set_title(titulo)
        ax.set_ylabel(rotulo_eixo)
        ax.tick_params(axis="x", labelsize=9)
        if usar_log:
            # Sem log o painel de dias fica ilegível: 173,99 dias do grupo sem linguagem primária
            # esmagam os ~2 dias dos outros dois, que é justamente a comparação da RQ04 aqui.
            ax.set_yscale("log")
            ax.set_ylim(top=valores.max() * 4)
        else:
            ax.set_ylim(0, valores.max() * 1.18)
        ax.bar_label(
            barras,
            labels=[formatar(valor) for valor in valores],
            padding=3,
            fontsize=9,
        )

    fig.suptitle(
        "RQ07 - Linguagens mais populares (top-10 TIOBE) vs. demais, nos 1.000 repositórios",
        fontsize=13,
        fontweight="bold",
    )
    legenda(fig)
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    return salvar(fig, nome)


def grafico_linguagens(tabela: pd.DataFrame, nome: str) -> str:
    """As 14 linguagens acima do corte, ordenadas por PRs aceitas e coloridas por grupo.

    A ordenação é a mesma nos três painéis de propósito: é assim que a intercalação aparece — Ruby
    (fora do top-10) na frente, Rust (top-10) em seguida, TypeScript e Go (fora) logo depois e
    Python (a primeira do TIOBE, e a maior da amostra) lá embaixo.
    """
    tabela = tabela.sort_values("mediana_prs_aceitas", ascending=True)
    rotulos = [
        f"{linguagem} ({int(repos)})"
        for linguagem, repos in zip(tabela["primary_language"], tabela["repos"])
    ]
    cores, hatches = cores_e_hatches(tabela["grupo"])

    fig, axes = plt.subplots(1, 3, figsize=(14, max(5, 0.45 * len(tabela))), sharey=True)
    for ax, (coluna, titulo, rotulo_eixo, usar_log) in zip(axes, METRICAS):
        valores = tabela[coluna]
        barras = ax.barh(rotulos, valores, color=cores, hatch=hatches)
        ax.set_title(titulo)
        ax.set_xlabel(rotulo_eixo.replace("mediana de ", "").replace("mediana ", ""))
        if usar_log:
            ax.set_xscale("log")
            positivos = valores[valores > 0]
            ax.set_xlim(left=positivos.min() * 0.6, right=valores.max() * 6)
        else:
            ax.set_xlim(0, valores.max() * 1.30)
        ax.bar_label(
            barras,
            labels=[formatar(valor) for valor in valores],
            padding=3,
            fontsize=8,
        )

    fig.suptitle(
        f"RQ07 - Medianas por linguagem primária "
        f"(linguagens com ao menos {MIN_REPOS_LINGUAGEM} repositórios)",
        fontsize=13,
        fontweight="bold",
    )
    legenda(fig)
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    return salvar(fig, nome)


def conferir_corte(tabela: pd.DataFrame) -> None:
    """Avisa se o CSV por linguagem veio sem o corte do `--min-repos` do analyze_rq07.py."""
    abaixo = tabela[tabela["repos"] < MIN_REPOS_LINGUAGEM]
    if not abaixo.empty:
        print(
            f"  AVISO - {len(abaixo)} linguagens abaixo de {MIN_REPOS_LINGUAGEM} repositórios no "
            f"CSV ({', '.join(abaixo['primary_language'])}). Regere com "
            f"--min-repos {MIN_REPOS_LINGUAGEM}: com uma ou duas linhas a 'mediana' é o próprio "
            "repositório (limitação 5 do README)."
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada-grupos", default="lab01/data/sprint_s02/rq07_top_vs_demais.csv")
    parser.add_argument("--entrada-linguagens", default="lab01/data/sprint_s02/rq07_por_linguagem.csv")
    args = parser.parse_args()

    setup_estilo()
    grupos = carregar_dados(args.entrada_grupos, COLUNAS_GRUPO)
    linguagens = carregar_dados(args.entrada_linguagens, COLUNAS_LINGUAGEM)

    total = int(grupos["repos"].sum())
    print(f"RQ07 - {total} repositórios em {len(grupos)} grupos e {len(linguagens)} linguagens")
    print("\nPor grupo:")
    print(grupos.to_string(index=False))

    top = grupos[grupos["grupo"] == GRUPO_TOP].iloc[0]
    demais = grupos[grupos["grupo"] == GRUPO_DEMAIS].iloc[0]
    vitorias = [
        demais["mediana_prs_aceitas"] > top["mediana_prs_aceitas"],
        demais["mediana_releases_por_ano"] > top["mediana_releases_por_ano"],
        # Invertida: em dias sem push, o menor vence.
        demais["mediana_dias_sem_push"] < top["mediana_dias_sem_push"],
    ]
    print(
        f"\nResposta da RQ07: {'NÃO' if all(vitorias) else 'ver tabela'} — "
        f"'{GRUPO_DEMAIS}' ganha em {sum(vitorias)} das 3 métricas "
        f"({formatar(demais['mediana_prs_aceitas'])} x {formatar(top['mediana_prs_aceitas'])} PRs, "
        f"{formatar(demais['mediana_releases_por_ano'])} x "
        f"{formatar(top['mediana_releases_por_ano'])} releases/ano, "
        f"{formatar(demais['mediana_dias_sem_push'])} x {formatar(top['mediana_dias_sem_push'])} "
        "dias sem push)."
    )
    print(
        f"  Não é idade: {formatar(demais['mediana_idade_anos'])} anos de mediana em "
        f"'{GRUPO_DEMAIS}' contra {formatar(top['mediana_idade_anos'])} em '{GRUPO_TOP}'."
    )

    print("\nPor linguagem:")
    print(linguagens.to_string(index=False))
    conferir_corte(linguagens)

    caminho_grupos = grafico_grupos(grupos, "rq07_grupos_tres_metricas")
    caminho_linguagens = grafico_linguagens(linguagens, "rq07_medianas_por_linguagem")
    print(f"\nGráficos salvos em {caminho_grupos} e {caminho_linguagens}")


if __name__ == "__main__":
    main()

"""RQ04: sistemas populares são atualizados com frequência? — days_since_last_push.

A resposta tem duas metades e os gráficos precisam mostrar as duas. A maior parte da amostra está
viva (mediana de 3,02 dias desde o último push, 60,6% com push na última semana), mas existe uma
cauda de repositórios que continuam estrelados por reputação acumulada e não recebem commit há
anos — 11,4% parados há mais de um ano, com `atom/atom` e `adobe/brackets` entre eles. A curva
acumulada mostra a primeira metade e a cauda do histograma, a segunda.

A métrica é `pushedAt`, não `updatedAt`: `updatedAt` muda com estrela, label e edição de descrição,
então por ele a mediana cairia para ~43 minutos e a cauda de abandonados sumiria do gráfico (ver
README, limitação `pushedAt` vs. `updatedAt`).
"""

import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from viz_common import PALETA, carregar_dados, marcar_mediana, salvar, setup_estilo

# Fronteira do "abandonado" nos dois gráficos: um ano sem push. É o corte que separa a cauda que
# sustenta a segunda metade da hipótese.
DIAS_ABANDONO = 365


def resumo(serie: pd.Series) -> dict:
    return {
        "repos": len(serie),
        "mediana": round(serie.median(), 2),
        "q1": round(serie.quantile(0.25), 2),
        "q3": round(serie.quantile(0.75), 2),
        "p90": round(serie.quantile(0.90), 2),
        "max": round(serie.max(), 2),
        "zeros": int((serie == 0).sum()),
        "abandonados": int((serie > DIAS_ABANDONO).sum()),
        "percentual_abandonados": round(100 * (serie > DIAS_ABANDONO).mean(), 1),
    }


def acumuladas(faixas: pd.DataFrame) -> pd.DataFrame:
    """Separa os pontos acumulados da linha de complemento do `rq04_faixas_push.csv`.

    O CSV termina com a linha "mais de 730 dias", que não é um ponto da curva: é o complemento da
    última faixa acumulada (6,6% = 100% - 93,4%). Plotá-la junto faria a curva despencar de 93,4%
    para 6,6% no fim, invertendo a leitura.
    """
    cumulativas = faixas[~faixas["ultimo_push_ate"].str.startswith("mais de")]
    # `expand=False` devolve Series em vez de DataFrame de uma coluna: com DataFrame, o `assign`
    # cai no caminho de atribuição encadeada que o pandas 3 deixa de suportar.
    dias = cumulativas["ultimo_push_ate"].str.extract(r"(\d+)", expand=False).astype(int)
    return cumulativas.assign(dias=dias).sort_values("dias")


def grafico_curva_acumulada(faixas: pd.DataFrame, nome: str) -> str:
    curva = acumuladas(faixas)

    fig, ax = plt.subplots()
    ax.plot(curva["dias"], curva["percentual"], marker="o", color=PALETA[0])
    for dias, percentual in zip(curva["dias"], curva["percentual"]):
        ax.annotate(
            f"{percentual:.1f}%".replace(".", ","),
            (dias, percentual),
            textcoords="offset points",
            xytext=(0, 9),
            ha="center",
            fontsize=9,
        )

    # Escala log no eixo x porque as faixas do CSV são geométricas (1, 7, 30, 90, 180, 365, 730):
    # em escala linear os cinco primeiros pontos ficariam empilhados junto da origem.
    ax.set_xscale("log")
    ax.set_xticks(curva["dias"])
    ax.set_xticklabels([str(dias) for dias in curva["dias"]])
    ax.set_title("RQ04 - Repositórios por tempo desde o último push (acumulado)")
    ax.set_xlabel("dias desde o último push (log)")
    ax.set_ylabel("% dos 1.000 repositórios (acumulado)")
    ax.set_ylim(0, 105)

    # A curva parar em 93,4% é o ponto do gráfico, não uma falha: o que falta para 100% é a cauda
    # de abandonados. A nota vai no canto vazio de baixo para não disputar espaço com o título.
    complemento = 100 - curva["percentual"].iloc[-1]
    ax.axhline(100, color="gray", linewidth=1, linestyle=":")
    ax.text(
        0.97,
        0.06,
        f"a curva não fecha em 100%: {complemento:.1f}% ({int(faixas['repos'].iloc[-1])} "
        "repositórios)\nseguem sem push há mais de 730 dias".replace(".", ","),
        transform=ax.transAxes,
        va="bottom",
        ha="right",
        fontsize=9,
        color="gray",
    )
    return salvar(fig, nome)


def grafico_histograma(serie: pd.Series, nome: str) -> str:
    # Escala log pelo mesmo motivo do viz_rq02: a métrica cobre mais de cinco ordens de grandeza
    # (de 0,01 a 2.448 dias) e em escala linear tudo colapsa no primeiro bin. Os repositórios com
    # 0,0 dia (push no momento da coleta) ficam de fora porque log(0) é indefinido — são reportados
    # à parte, no log do script.
    positivos = serie[serie > 0]
    # `nextafter` na borda final: sem ele o arredondamento de ponto flutuante deixa o último bin um
    # fio abaixo do máximo real e o repositório mais parado de todos some do gráfico.
    bins = np.logspace(np.log10(positivos.min()), np.log10(np.nextafter(positivos.max(), np.inf)), 30)

    fig, ax = plt.subplots()
    ax.hist(positivos, bins=bins)
    ax.set_xscale("log")

    # A cauda de abandonados é a segunda metade da hipótese, então é destacada em vez de ficar só
    # implícita nas barras baixas da direita.
    abandonados = int((serie > DIAS_ABANDONO).sum())
    ax.axvspan(DIAS_ABANDONO, bins[-1], color=PALETA[3], alpha=0.12)
    # Acima da barra mais alta da cauda, para o texto não cobrir o cluster de ~700-1.000 dias.
    ax.text(
        DIAS_ABANDONO * 1.15,
        ax.get_ylim()[1] * 0.97,
        f"{abandonados} repositórios ({round(100 * abandonados / len(serie), 1)}%)".replace(".", ",")
        + f"\nsem push há mais de {DIAS_ABANDONO} dias",
        fontsize=9,
        va="top",
    )

    ax.set_title("RQ04 - Distribuição do tempo desde o último push (escala log)")
    ax.set_xlabel("dias desde o último push (log)")
    ax.set_ylabel("repositórios")
    mediana = round(serie.median(), 2)
    marcar_mediana(ax, mediana, rotulo=f"mediana = {mediana} dias")
    return salvar(fig, nome)


def comparar_push_update(df: pd.DataFrame) -> dict:
    """Mede o que a troca de `pushedAt` por `updatedAt` faria com a RQ04.

    É a justificativa da escolha da métrica, e o relatório precisa dela: `updatedAt` muda com
    estrela, label e edição de descrição, coisas sem relação com desenvolvimento.
    """
    push = df["days_since_last_push"]
    update = df["days_since_last_update"]
    return {
        "mediana_push": round(push.median(), 2),
        "mediana_update_minutos": round(update.median() * 24 * 60, 1),
        "update_mais_recente": int((update < push).sum()),
        "abandonados_por_push": int((push > DIAS_ABANDONO).sum()),
        "abandonados_por_update": int((update > DIAS_ABANDONO).sum()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", default="lab01/data/sprint_s02/all_rqs.csv")
    parser.add_argument("--faixas", default="lab01/data/sprint_s02/rq04_faixas_push.csv")
    args = parser.parse_args()

    setup_estilo()
    df = carregar_dados(args.entrada, ["repo", "days_since_last_push", "days_since_last_update"])
    serie = df["days_since_last_push"]
    faixas = carregar_dados(args.faixas, ["ultimo_push_ate", "repos", "percentual"])

    stats = resumo(serie)
    print(
        f"RQ04 - {stats['repos']} repositórios | mediana {stats['mediana']} dias desde o último "
        f"push (Q1 {stats['q1']}, Q3 {stats['q3']}, p90 {stats['p90']}, máx {stats['max']})"
    )
    curva = acumuladas(faixas)
    for dias, repos, percentual in zip(curva["dias"], curva["repos"], curva["percentual"]):
        print(f"  push nos últimos {dias:>3} dia(s): {repos:>4} repositórios ({percentual}%)")
    print(
        f"  cauda: {stats['abandonados']} repositórios ({stats['percentual_abandonados']}%) sem "
        f"push há mais de {DIAS_ABANDONO} dias"
    )
    print(f"  {stats['zeros']} repositórios com 0,0 dia ficam fora do histograma (log(0))")

    comparacao = comparar_push_update(df)
    print(
        f"  pushedAt vs. updatedAt - mediana {comparacao['mediana_push']} dias contra "
        f"{comparacao['mediana_update_minutos']} minutos; por updatedAt a cauda cai de "
        f"{comparacao['abandonados_por_push']} para {comparacao['abandonados_por_update']} "
        "repositórios parados há mais de um ano"
    )

    caminho_curva = grafico_curva_acumulada(faixas, "rq04_curva_acumulada_push")
    caminho_hist = grafico_histograma(serie, "rq04_histograma_dias_push_log")
    print(f"Gráficos salvos em {caminho_curva} e {caminho_hist}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""RQ1 (tempo) e RQ2 (defeitos): com_ia x sem_ia (Issue #61)."""

from pathlib import Path

import pandas as pd
from scipy.stats import rankdata, wilcoxon

RAIZ = Path(__file__).resolve().parents[1]
CSV = RAIZ / "data" / "trials.csv"
SAIDA = RAIZ / "resultados"
TRATAMENTOS = ["com_ia", "sem_ia"]


def iqr(s):
    return s.quantile(0.75) - s.quantile(0.25)


def outliers(df, col):
    q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
    lim = 1.5 * (q3 - q1)
    fora = df[(df[col] < q1 - lim) | (df[col] > q3 + lim)]
    return ", ".join(f"{r.integrante}/{r.kata}" for r in fora.itertuples()) or "-"


def pares(df, col):
    df = df.assign(bloco=(df["ordem"] + 1) // 2)
    p = df.pivot_table(index=["integrante", "bloco"], columns="tratamento", values=col).dropna()
    return p["com_ia"] - p["sem_ia"]


def rank_biserial(d):
    d = d[d != 0]
    r = rankdata(abs(d))
    pos, neg = r[d > 0].sum(), r[d < 0].sum()
    return (pos - neg) / (pos + neg)


def resumo(df, col, por):
    g = df.groupby(por)[col]
    return pd.DataFrame({"n": g.size(), "mediana": g.median(), "iqr": g.apply(iqr)}).round(4).reset_index()


def tabela(df):
    linhas = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    linhas += ["| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(index=False)]
    return "\n".join(linhas)


def main():
    df = pd.read_csv(CSV)
    df["testes_falhando"] = df["testes_total"] - df["testes_passando"]
    censurado = df["censurado_35min"].astype(str).str.lower() == "true"

    rq1 = resumo(df, "tempo_s", "tratamento")
    rq1["censurados"] = [int(censurado[df["tratamento"] == t].sum()) for t in rq1["tratamento"]]
    rq1["outliers"] = [outliers(df[df["tratamento"] == t], "tempo_s") for t in rq1["tratamento"]]

    d = pares(df, "tempo_s")
    res = wilcoxon(d, alternative="less", method="exact")
    teste = pd.DataFrame([{
        "n_pares": len(d),
        "W": res.statistic,
        "p_valor": round(res.pvalue, 4),
        "rank_biserial": round(rank_biserial(d), 4),
    }])

    por_integrante = resumo(df, "tempo_s", ["integrante", "tratamento"])
    por_kata = resumo(df, "tempo_s", ["kata", "tratamento"])

    rq2 = resumo(df, "taxa_sucesso", "tratamento")
    rq2["testes_falhando"] = [int(df.loc[df["tratamento"] == t, "testes_falhando"].sum()) for t in rq2["tratamento"]]
    variacao = df["taxa_sucesso"].nunique() > 1

    SAIDA.mkdir(exist_ok=True)
    rq1.to_csv(SAIDA / "rq1_descritiva.csv", index=False)
    teste.to_csv(SAIDA / "rq1_wilcoxon.csv", index=False)
    por_integrante.to_csv(SAIDA / "rq1_por_integrante.csv", index=False)
    por_kata.to_csv(SAIDA / "rq1_por_kata.csv", index=False)
    rq2.to_csv(SAIDA / "rq2_descritiva.csv", index=False)

    md = [
        "# RQ1 e RQ2",
        "",
        "## RQ1: tempo (s)",
        "",
        tabela(rq1),
        "",
        "Wilcoxon pareado exato, unilateral (com_ia < sem_ia), pares por ordem (1-2 e 3-4):",
        "",
        tabela(teste),
        "",
        "Por integrante:",
        "",
        tabela(por_integrante),
        "",
        "Por kata:",
        "",
        tabela(por_kata),
        "",
        "## RQ2: taxa de sucesso",
        "",
        tabela(rq2),
        "",
        "Com variação, dá pra testar." if variacao else "Todos os trials passaram em tudo, então não tem o que testar.",
        "",
    ]
    (SAIDA / "rq1_rq2.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()

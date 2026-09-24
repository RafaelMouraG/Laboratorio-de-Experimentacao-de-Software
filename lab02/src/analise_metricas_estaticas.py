"""RQ3 (métricas estáticas): com_ia x sem_ia (Issue #62)."""

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
    return ", ".join(f"{r.integrante}/{r.kata} ({getattr(r, col):.2f})" for r in fora.itertuples()) or "-"

def pares(df, col):
    df = df.assign(bloco=(df["ordem"] + 1) // 2)
    p = df.pivot_table(index=["integrante", "bloco"], columns="tratamento", values=col).dropna()
    return p["com_ia"] - p["sem_ia"]

def rank_biserial(d):
    d = d[d != 0]
    if len(d) == 0:
        return 0.0
    r = rankdata(abs(d))
    pos, neg = r[d > 0].sum(), r[d < 0].sum()
    if pos + neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)

def tabela(df):
    linhas = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    linhas += ["| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(index=False)]
    return "\n".join(linhas)

def main():
    df = pd.read_csv(CSV)
    
    # Complexidade normalizada por tamanho
    df["cc_por_loc"] = df["cc_media"] / df["loc"]
    
    metricas = ["loc", "cc_media", "cc_por_loc", "mi", "duplicacao_pct"]
    
    # Resumo descritivo: mediana e IQR
    linhas_desc = []
    for t in TRATAMENTOS:
        df_t = df[df["tratamento"] == t]
        linha = {"tratamento": t, "n": len(df_t)}
        for m in metricas:
            linha[f"{m}_med"] = round(df_t[m].median(), 4)
            linha[f"{m}_iqr"] = round(iqr(df_t[m]), 4)
        linhas_desc.append(linha)
    
    desc = pd.DataFrame(linhas_desc)
    
    # Outliers
    outliers_list = []
    for m in metricas:
        for t in TRATAMENTOS:
            df_t = df[df["tratamento"] == t]
            o = outliers(df_t, m)
            if o != "-":
                outliers_list.append(f"- **{m}** ({t}): {o}")
    if not outliers_list:
        outliers_list.append("- Nenhum outlier detectado (critério 1,5x IQR).")
    
    # Teste de Hipótese (Wilcoxon)
    zero_method = "pratt"
    testes = []
    
    for m in ["cc_media", "cc_por_loc", "mi"]:
        d = pares(df, m)
        if len(d) == 0 or (d == 0).all():
            testes.append({
                "metrica": m,
                "n_pares": len(d),
                "W": "-",
                "p_valor": "-",
                "rank_biserial": "-",
                "obs": "sem variação suficiente"
            })
            continue
            
        res = wilcoxon(d, alternative="two-sided", method="exact", zero_method=zero_method)
        testes.append({
            "metrica": m,
            "n_pares": len(d),
            "W": res.statistic,
            "p_valor": round(res.pvalue, 4),
            "rank_biserial": round(rank_biserial(d), 4),
            "obs": ""
        })
        
    df_testes = pd.DataFrame(testes)
    
    # Duplicação
    var_duplicacao = df["duplicacao_pct"].nunique() > 1
    
    SAIDA.mkdir(exist_ok=True)
    desc.to_csv(SAIDA / "rq3_descritiva.csv", index=False)
    df_testes.to_csv(SAIDA / "rq3_wilcoxon.csv", index=False)
    
    md = [
        "# RQ3: Métricas Estáticas",
        "",
        "## Estatística Descritiva",
        "",
        "Mediana e IQR por tratamento. `loc` atua como controle de tamanho para complexidade e duplicação.",
        "",
        tabela(desc),
        "",
        "### Outliers",
        "",
        "Identificados pelo critério 1,5 × IQR. Decisão registrada: mantê-los para não reduzir ainda mais o N (já pequeno, 12). Wilcoxon lida razoavelmente bem com outliers.",
        "",
        *outliers_list,
        "",
        "## Teste de Hipótese",
        "",
        f"Wilcoxon pareado exato, bilateral (H1: há diferença). Pareamento por ordem (1-2 e 3-4, mesmo de RQ1/RQ2).",
        f"Atenção aos empates (como 4 × 4 do RafaelMouraG): `zero_method='{zero_method}'` inclui diferenças zero no ranqueamento, mas descarta da soma de postos. Isso preserva a validade do teste exato para a amostra sem inflacionar a significância.",
        "Tratada como exploratória (múltiplas comparações), sem afirmação de significância isolada.",
        "",
        tabela(df_testes),
        "",
        "## Duplicação",
        "",
        "Houve variação?" if var_duplicacao else "A métrica `duplicacao_pct` é 0.0 em todos os 12 trials. Relatado como ausência de variação, sem forçar teste.",
        ""
    ]
    
    (SAIDA / "rq3.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))

if __name__ == "__main__":
    main()

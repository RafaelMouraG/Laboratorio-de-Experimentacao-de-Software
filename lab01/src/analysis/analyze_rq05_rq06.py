"""RQ05 e RQ06: Linguagens populares e Razão de Issues fechadas"""

import argparse
import os
import sys

import pandas as pd

def carregar(caminho: str, colunas: list[str]) -> pd.DataFrame:
    if not os.path.exists(caminho):
        sys.exit(f"{caminho} não encontrado. Rode antes os scripts de coleta das RQ01-RQ06.")

    df = pd.read_csv(caminho, keep_default_na=False)
    faltando = [coluna for coluna in colunas if coluna not in df.columns]
    if faltando:
        sys.exit(f"{caminho}: colunas ausentes {faltando}")
    return df[colunas]

def analisar_rq05(df: pd.DataFrame) -> None:
    print("\n" + "="*40)
    print("RQ05: LINGUAGEM PRIMÁRIA")
    print("="*40)
    
    total = len(df)
    qtd_na = (df['primary_language'] == 'N/A').sum()
    print(f"Total de repositórios: {total}")
    print(f"Repositórios sem linguagem (N/A): {qtd_na} ({qtd_na/total*100:.1f}%)\n")
    
    print("Top 15 linguagens mais frequentes:")
    print(df['primary_language'].value_counts().head(15).to_string())

def analisar_rq06(df: pd.DataFrame) -> None:
    print("\n" + "="*40)
    print("RQ06: RAZÃO DE ISSUES FECHADAS")
    print("="*40)
    
    sem_issues = df[df['total_issues'] == 0]
    print(f"Repositórios com 0 issues no total: {len(sem_issues)}")
    print(f"Razão calculada para esses casos: {list(sem_issues['closed_issues_ratio'].unique())}\n")
    
    print("Estatísticas DESCARTANDO os repositórios com 0 issues:")
    df_valido = df[df['total_issues'] > 0]
    
    resumo = {
        "Repos Válidos": len(df_valido),
        "Mediana": round(df_valido['closed_issues_ratio'].median(), 4),
        "Média": round(df_valido['closed_issues_ratio'].mean(), 4),
        "Q1 (25%)": round(df_valido['closed_issues_ratio'].quantile(0.25), 4),
        "Q3 (75%)": round(df_valido['closed_issues_ratio'].quantile(0.75), 4)
    }
    
    for k, v in resumo.items():
        print(f"{k}: {v}")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", default="lab01/data/sprint_s02/all_rqs.csv")
    args = parser.parse_args()

    df = carregar(args.entrada, ["repo", "primary_language", "total_issues", "closed_issues_ratio"])
    
    analisar_rq05(df)
    analisar_rq06(df)

if __name__ == "__main__":
    main()

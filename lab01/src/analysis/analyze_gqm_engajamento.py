import pandas as pd

def analyze_gqm():
    csv_path = "lab01/data/sprint_s02/all_rqs.csv"
    
    try:
        df = pd.read_csv(csv_path, keep_default_na=False)
    except FileNotFoundError:
        print(f"Erro: Arquivo {csv_path} não encontrado.")
        return

    df_valid = df[df['total_issues'] > 0].copy()
    
    df_valid['merged_pull_requests'] = pd.to_numeric(df_valid['merged_pull_requests'], errors='coerce')
    df_valid['closed_issues_ratio'] = pd.to_numeric(df_valid['closed_issues_ratio'], errors='coerce')
    df_valid = df_valid.dropna(subset=['merged_pull_requests', 'closed_issues_ratio'])

    correlation = df_valid['merged_pull_requests'].corr(df_valid['closed_issues_ratio'])
    
    print("--- Resultados GQM ---")
    print(f"Repositórios válidos analisados: {len(df_valid)}")
    print(f"Correlação de Pearson: {correlation:.4f}")

if __name__ == "__main__":
    analyze_gqm()

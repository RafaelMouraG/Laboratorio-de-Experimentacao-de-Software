import csv
import os

def gerar_template_coleta(integrantes, katas):
    """
    Gera o template de coleta de dados para a S02 com base no design crossover.
    """
    linhas_coleta = []
    
    padroes = [
        ["Com IA", "Sem IA", "Com IA", "Sem IA"],
        ["Sem IA", "Com IA", "Sem IA", "Com IA"],
        ["Com IA", "Com IA", "Sem IA", "Sem IA"]
    ]
    
    for i, integrante in enumerate(integrantes):
        padrao = padroes[i % len(padroes)]
        for j, kata in enumerate(katas):
            tratamento = padrao[j % len(padrao)]
            linha = {
                "Integrante": integrante,
                "Kata": kata,
                "Tratamento": tratamento,
                "Tempo_Resolucao_Min": "",         
                "Testes_Passando": "",            
                "Total_Testes_Kata": "",          
                "LOC": "",                        
                "Complexidade_Ciclomatica": "",   
                "Duplicacao_Codigo_Perc": ""
            }
            linhas_coleta.append(linha)
            
    return linhas_coleta

def salvar_csv(dados, caminho_saida):
    if not dados:
        return
        
    header = list(dados[0].keys())
    with open(caminho_saida, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(dados)

if __name__ == "__main__":
    integrantes = ["Integrante A", "Integrante B", "Integrante C"]
    katas = ["K1", "K2", "K3", "K4"]
    
    dados = gerar_template_coleta(integrantes, katas)
    
    caminho_saida = os.path.join(os.path.dirname(__file__), "template_coleta_dados_s02.csv")
    salvar_csv(dados, caminho_saida)
    
    print(f"Template de coleta com {len(dados)} trials gerado com sucesso!")
    print(f"Arquivo salvo em: {caminho_saida}")
    print("\nColunas criadas para preenchimento na Sprint 2:")
    for col in dados[0].keys():
        print(f"- {col}")

# Desenho do Experimento (Lab 02)

## 1. Hipóteses (H0 e H1)
**RQ1: O uso de assistente de IA reduz o tempo necessário para resolver uma tarefa de programação?**
* **H0:** O tempo mediano de resolução com IA é *maior ou igual* ao tempo manual ($T_{IA} \ge T_{Manual}$).
* **H1:** O tempo mediano de resolução com IA é *menor* que o tempo manual ($T_{IA} < T_{Manual}$).

**RQ2: O uso de assistente de IA reduz a quantidade de defeitos (testes que falham) no código produzido?**
* **H0:** A taxa mediana de sucesso nos testes com IA é *menor ou igual* à da codificação manual ($S_{IA} \le S_{Manual}$).
* **H1:** A taxa mediana de sucesso nos testes com IA é *maior* do que na codificação manual ($S_{IA} > S_{Manual}$).

**RQ3: O uso de assistente de IA altera a complexidade ciclomática ou a duplicação do código produzido?**
* **H0:** Não há diferença estatisticamente significativa na complexidade ciclomática mediana e na duplicação de código entre as abordagens ($C_{IA} = C_{Manual}$).
* **H1:** Há diferença estatisticamente significativa na complexidade ciclomática mediana e/ou na duplicação de código entre as abordagens ($C_{IA} \ne C_{Manual}$).

## 2. Variáveis Dependentes e Independentes
* **Variável Independente (VI):** Uso de assistente de IA (Níveis: Com IA vs. Sem IA / Manual).
* **Variáveis Dependentes (VD):**
  * **VD1 (RQ1):** Tempo de resolução "time-to-green" (minutos). Limitado a 35 min (censurado em caso de falha).
  * **VD2 (RQ2):** Taxa de sucesso (% de testes de aceitação passando).
  * **VD3 (RQ3):** Complexidade ciclomática e Porcentagem de código duplicado, controladas por LOC.

## 3. Tratamentos
* **Tratamento 1 (Controle):** Codificação manual. O programador resolve o kata com a IDE, sem IA generativa.
* **Tratamento 2 (Experimental):** Codificação com assistente de IA. O programador resolve o kata utilizando a ferramenta de IA escolhida pelo grupo.

## 4. Projeto Crossover Within-Subject Contrabalanceado
O experimento utiliza um desenho *within-subject* (todos testam ambos os tratamentos), em formato *crossover* (alternando tratamentos) e *contrabalanceado* (variando a ordem entre integrantes para mitigar efeito de aprendizado/cansaço).

### Tabela de Ordem (3 Integrantes, 4 Katas)
| Integrante | K1 | K2 | K3 | K4 |
| :--- | :--- | :--- | :--- | :--- |
| **Integrante A** | Com IA | Sem IA | Com IA | Sem IA |
| **Integrante B** | Sem IA | Com IA | Sem IA | Com IA |
| **Integrante C** | Com IA | Com IA | Sem IA | Sem IA |

*(O planejamento da execução de cada trial, além da criação do template oficial de planilha para coleta das métricas na Sprint 2, é gerado de forma automatizada pelo script `gerar_tabela_contrabalanceamento.py` (que consolida os dados no arquivo `template_coleta_dados_s02.csv`) disponibilizado neste repositório).*

## 5. Número de Medições
* Integrantes: 3
* Katas: 4
* **Total:** 12 medições (6 com IA, 6 sem IA).

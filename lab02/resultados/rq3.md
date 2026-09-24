# RQ3: Métricas Estáticas

## Estatística Descritiva

Mediana e IQR por tratamento. `loc` atua como controle de tamanho para complexidade e duplicação.

| tratamento | n | loc_med | loc_iqr | cc_media_med | cc_media_iqr | cc_por_loc_med | cc_por_loc_iqr | mi_med | mi_iqr | duplicacao_pct_med | duplicacao_pct_iqr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| com_ia | 6 | 14.5 | 4.5 | 4.5 | 4.0 | 0.3818 | 0.1966 | 88.98 | 4.7975 | 0.0 | 0.0 |
| sem_ia | 6 | 13.0 | 10.0 | 4.0 | 3.75 | 0.3239 | 0.0704 | 88.6394 | 9.8056 | 0.0 | 0.0 |

### Outliers

Identificados pelo critério 1,5 × IQR. Decisão registrada: mantê-los para não reduzir ainda mais o N (já pequeno, 12). Wilcoxon lida razoavelmente bem com outliers.

- **cc_por_loc** (sem_ia): Athoosz/k3 (0.55)

## Teste de Hipótese

Wilcoxon pareado exato, bilateral (H1: há diferença). Pareamento por ordem (1-2 e 3-4, mesmo de RQ1/RQ2).
Atenção aos empates (como 4 × 4 do RafaelMouraG): `zero_method='pratt'` inclui diferenças zero no ranqueamento, mas descarta da soma de postos. Isso preserva a validade do teste exato para a amostra sem inflacionar a significância.
Tratada como exploratória (múltiplas comparações), sem afirmação de significância isolada.

| metrica | n_pares | W | p_valor | rank_biserial | obs |
|---|---|---|---|---|---|
| cc_media | 6 | 8.5 | 1.0 | 0.1333 |  |
| cc_por_loc | 6 | 4.0 | 0.3125 | 0.6 |  |
| mi | 6 | 9.0 | 0.8438 | 0.1429 |  |

## Duplicação

A métrica `duplicacao_pct` é 0.0 em todos os 12 trials. Relatado como ausência de variação, sem forçar teste.

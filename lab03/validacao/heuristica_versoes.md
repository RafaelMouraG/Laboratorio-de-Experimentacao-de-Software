# Versões da heurística de release corretiva

Gerado por `python -m lab03.validacao.avaliar_heuristica`. Cada versão roda nas 300 releases da amostra-ouro e é comparada com o consenso dos três avaliadores (115 corretivas). A versão usada na CFR (b) é a **v4**.

| Versão | Regra | Precisão | Recall | F1 | Marcadas |
|---|---|---|---|---|---|
| v1 | só o patch subiu em relação à anterior **ou** algum commit com `fix`, `hotfix` ou `revert` | 0.399 | 0.965 | 0.565 | 278 |
| v2 | só o patch subiu em relação à anterior **e** algum commit com `fix`, `hotfix` ou `revert` | 0.541 | 0.626 | 0.581 | 133 |
| v3 | o patch da própria versão é maior que zero (`x.y.z`, `z > 0`), sem olhar a anterior | 0.542 | 0.904 | 0.678 | 192 |
| v4 | v3 **e** as notas da release citam correção (`fix`, `bug`) pelo menos tantas vezes quanto novidade (`feat`, `feature`, `add`, `new`, `introduce`, `support`) | 0.673 | 0.861 | 0.756 | 147 |

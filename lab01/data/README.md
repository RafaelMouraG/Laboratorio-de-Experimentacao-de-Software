# Estrutura de dados (Lab01)

- **`amostra/`** — validações rápidas 10 repositórios, uma por integrante, antes de integrar o campo/métrica ao script único do grupo, nao é o entregavel.

- **`sprint_s01/`** — consulta real dos 100 repositórios. Cada integrante gera aqui o CSV com os campos da sua dupla de RQs; ao final da sprint esses campos devem estar unificados num único script/CSV com todos os dados.

No final tem que dar pra cruzar tudo por repositório (idade, PRs merged, releases, última atualização, linguagem, issues...), então quando for integrar não pode ficar em CSVs separados sem um jeito de juntar (mesmo repo em todos).

Isso importa principalmente pro RQ07 (bônus): ele cruza os resultados de RQ02/03/04 com a linguagem de cada repo (RQ05). Já que não tem mais uma pessoa fixa pro RQ07, ficou combinado que cada um agrupa por linguagem o resultado da própria métrica dentro da própria issue (ex: quem faz RQ02 também entrega RQ02 agrupado por linguagem, e assim por diante pra RQ03 e RQ04).

O `sprint_s01/all_rqs.csv` é esse CSV unificado: sai do `src/collection/collect_all_rqs.py` e já traz as seis RQs por repositório, com os mesmos nomes de coluna dos CSVs por dupla de RQ (`releases`, `days_since_last_push`, `primary_language`...).

> Os snapshots do Kanban **não** ficam aqui — eles atravessam todos os laboratórios e moram em [`kanban/snapshots/`](../../kanban/README.md).

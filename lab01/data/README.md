# Estrutura de dados (Lab01)

- **`amostra/`** — validações rápidas 10 repositórios, uma por integrante, antes de integrar o campo/métrica ao script único do grupo, nao é o entregavel.

- **`sprint_s01/`** — consulta real dos 100 repositórios, já unificada num único CSV.

- **`sprint_s02/`** — mesma consulta, elevada para os 1.000 repositórios (teto da busca do GitHub). Mesmas colunas de `sprint_s01/all_rqs.csv`, gerado pelo mesmo script.

No final tem que dar pra cruzar tudo por repositório (idade, PRs merged, releases, última atualização, linguagem, issues...), então a coleta não fica em CSVs separados por dupla de RQ — fica tudo junto, num só arquivo, pra não correr o risco de duas fontes divergirem entre si.

Isso importa principalmente pro RQ07: ele cruza os resultados de RQ02/03/04 com a linguagem de cada repo (RQ05).

O `all_rqs.csv` de cada sprint sai do `src/collection/collect_all_rqs.py` (`--n 100` ou `--n 1000`) e traz as seis RQs por repositório. É a única fonte de dados da sprint correspondente — todo script de análise (`analyze_rq03.py`, `analyze_rq07.py`, `extra_idade_vs_popularidade.py`) lê dele por padrão, com o caminho trocável via `--entrada`. Os CSVs por dupla de RQ que cada integrante gerava em `sprint_s01/` durante a validação inicial foram removidos depois da unificação: `collect_sample_rq0X_rq0Y.py` continua existindo só para a validação rápida (10 repositórios) de cada integrante, salva em `amostra/`.

> Os snapshots do Kanban **não** ficam aqui — eles atravessam todos os laboratórios e moram em [`kanban/snapshots/`](../../kanban/README.md).

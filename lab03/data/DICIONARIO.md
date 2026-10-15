# Dicionário de dados

Todos os CSVs são UTF-8, separados por vírgula. Campos vazios significam que a
coleta necessária ainda não terminou ou que não há observação válida; vazio não
é sinônimo de zero.

## `repos.csv`

| Coluna | Tipo | Unidade | Origem |
|---|---|---|---|
| `repo` | texto | `owner/name` | API, `full_name` |
| `estrelas` | inteiro | estrelas | API, `stargazers_count` |
| `linguagem` | texto | — | API, `language` |
| `default_branch` | texto | — | API, `default_branch` |
| `criado_em` | data-hora ISO 8601 | UTC | API, `created_at` |
| `idade_anos` | real | anos | fórmula: data final da janela menos `criado_em` |
| `contribuidores` | inteiro | pessoas | API de contribuidores |
| `releases` | inteiro | releases | contagem de releases publicadas na janela |
| `releases_sem_anterior` | inteiro | releases | contagem de releases sem release anterior |
| `releases_ignoradas_compare_404` | inteiro | releases | compare que retornou 404 |
| `commits_releases` | inteiro | commits | soma dos commits entre releases |
| `runs_validos` | inteiro | runs | runs de CI com conclusão `success`, `failure`, `timed_out` ou `startup_failure` |
| `runs_sucesso` | inteiro | runs | subset dos runs válidos com `success` |
| `runs_falha` | inteiro | runs | subset dos runs válidos com conclusão de falha |

## `releases.csv`

| Coluna | Tipo | Unidade | Origem |
|---|---|---|---|
| `repo` | texto | `owner/name` | repositório da coleta |
| `tag_name` | texto | — | API de releases, `tag_name` |
| `published_at` | data-hora ISO 8601 | UTC | API de releases, `published_at` |
| `prerelease` | booleano | — | API de releases, `prerelease` |
| `html_url` | texto | URL | API de releases, `html_url` |
| `commits` | inteiro | commits | tamanho do compare com a release anterior |
| `sem_anterior` | booleano | — | fórmula: não existe release estável anterior |
| `ignorada_compare_404` | booleano | — | fórmula: compare da release foi ignorado por 404 |

## `funil.csv`

| Coluna | Tipo | Unidade | Origem |
|---|---|---|---|
| `ordem` | inteiro | — | ordem da etapa no funil |
| `etapa` | texto | — | nome da etapa do pipeline |
| `restantes` | inteiro | repositórios | contagem após a etapa |
| `descartados` | inteiro | repositórios | diferença para a etapa anterior |
| `motivo` | texto | — | motivo(s) de descarte e suas contagens |

## `metricas.csv`

Cada linha corresponde a um repositório aceito. As faixas são inteiros de 1
(Low) a 4 (Elite), conforme as fronteiras em `metricas/classificacao.py`.

| Coluna | Tipo | Unidade | Origem |
|---|---|---|---|
| `repo` | texto | `owner/name` | `resultado["repo"]` |
| `releases_por_semana` | real | releases/semana | releases publicadas na janela / duração da janela em semanas |
| `faixa_releases` | inteiro | faixa DORA 1–4 | `faixa_frequencia(releases_por_semana)` |
| `lead_time_release_horas` | real | horas | mediana de `published_at - commit mais antigo` por release |
| `lead_time_release_avaliadas` | inteiro | releases | releases com commits válidos e release anterior |
| `lead_time_release_descartados` | inteiro | commits | commits posteriores à publicação |
| `faixa_lead_time_release` | inteiro | faixa DORA 1–4 | `faixa_lead_time` da variante por release |
| `lead_time_commit_horas` | real | horas | mediana de `published_at - commit` de todos os commits válidos |
| `lead_time_commit_avaliadas` | inteiro | commits | commits válidos usados na mediana |
| `lead_time_commit_descartados` | inteiro | commits | commits posteriores à publicação |
| `faixa_lead_time_commit` | inteiro | faixa DORA 1–4 | `faixa_lead_time` da variante por commit |
| `cfr_ci` | fração real | 0 a 1 | runs de falha / (runs de falha + sucesso) |
| `cfr_ci_avaliadas` | inteiro | runs | conclusões que entram na CFR |
| `cfr_ci_censuradas` | inteiro | runs | conclusões ignoradas (cancelled, skipped etc.) |
| `faixa_cfr_ci` | inteiro | faixa DORA 1–4 | `faixa_cfr(cfr_ci)` |
| `cfr_entrega` | fração real | 0 a 1 | `cfr_entrega_falharam / cfr_entrega_avaliadas` (`metricas/corretiva.py`) |
| `cfr_entrega_avaliadas` | inteiro | releases | releases publicadas pelo menos 7 dias antes do fim da janela |
| `cfr_entrega_falharam` | inteiro | releases | avaliadas cuja release seguinte sai em até 7 dias e é corretiva pela heurística (`eh_corretiva`, versão em `heuristica_versoes.md`) |
| `cfr_entrega_censuradas` | inteiro | releases | publicadas nos últimos 7 dias da janela |
| `faixa_cfr_entrega` | inteiro | faixa DORA 1–4 | `faixa_cfr(cfr_entrega)` |
| `recuperacao_mediana_horas` | real | horas | mediana dos episódios fechados de falha de CI |
| `recuperacao_episodios` | inteiro | episódios | episódios de falha após o primeiro sucesso do workflow |
| `recuperacao_censurados` | inteiro | episódios | episódios sem sucesso posterior na janela |
| `recuperacao_proporcao_censurados` | fração real | 0 a 1 | episódios censurados / episódios |
| `faixa_recuperacao` | inteiro | faixa DORA 1–4 | `faixa_recuperacao` da mediana |
| `classificacao_geral` | inteiro | faixa DORA 1–4 | mediana inteira da combinação de referência: releases, lead time por release e CFR de CI |

O `metricas.csv` é gravado pelo pipeline somente quando a janela é conhecida.
Em execução parcial, repositórios ainda sem coleta pesada aparecem com métricas
vazias, preservando a distinção entre ausência de dados e valor zero.

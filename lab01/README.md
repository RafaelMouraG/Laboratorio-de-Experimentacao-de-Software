# Lab01 — Características de repositórios populares + Setup do Kanban

| LAB01 | Laboratório 01 - 15 pontos |
|---|---|

> Setup do ambiente (`.env`, `.venv`, dependências) está no [README da raiz](../README.md).
> Todos os comandos abaixo rodam **a partir da raiz do repositório**.

Neste laboratório, vamos estudar as principais características de sistemas populares open-source, dando início também ao uso do quadro Kanban que acompanhará o grupo durante todo o semestre. Para a parte de mineração, colete os dados indicados a seguir para os 1.000 repositórios com maior número de estrelas no GitHub e discuta os valores obtidos.

## Parte 1 — Questões de Pesquisa

**RQ 01.** Sistemas populares são maduros/antigos?
Métrica: idade do repositório (calculado a partir da data de sua criação)

**RQ 02.** Sistemas populares recebem muita contribuição externa?
Métrica: total de pull requests aceitas

**RQ 03.** Sistemas populares lançam releases com frequência?
Métrica: total de releases

**RQ 04.** Sistemas populares são atualizados com frequência?
Métrica: tempo até a última atualização

**RQ 05.** Sistemas populares são escritos nas linguagens mais populares?
Métrica: linguagem primária de cada repositório
*(defina e referencie explicitamente a fonte usada para "linguagens mais populares" — ex.: TIOBE Index, GitHut ou o Octoverse do GitHub — mantendo a mesma referência ao longo de todo o laboratório)*

**RQ 06.** Sistemas populares possuem um alto percentual de issues fechadas?
Métrica: razão entre issues fechadas e total de issues

**Bônus (+1 ponto) — RQ 07:** Sistemas escritos em linguagens mais populares recebem mais contribuição externa, lançam mais releases e são atualizados com mais frequência? (divida os resultados das RQs 02, 03 e 04 por linguagem)

## Parte 2 — Setup do GitHub Projects do grupo

O grupo (trio) deve constituir, a partir deste laboratório, o GitHub Projects (v2) que será usado até o final do semestre. Defina e documente:

1. **Crie um GitHub Projects (v2)** vinculado ao repositório do grupo.
2. **Cartões = Issues** do repositório, adicionadas ao Project (não usar "draft issues" soltas — cada tarefa deve virar uma Issue de verdade, rastreável pela API) e **atribuídas a um responsável** (campo Assignee).
3. **Colunas do board** (campo Status): no mínimo `Backlog → To Do → Doing → Review → Done`.
4. **Limite de WIP** (Work in Progress) para a coluna Doing — defina e justifique o número escolhido.
5. Todas as tarefas do próprio Lab01 (e dos laboratórios seguintes) devem ser quebradas em Issues e movimentadas no board conforme o progresso real do grupo, não retroativamente.
6. **Snapshot de fechamento de sprint:** ao final de cada sprint (Lab01S01, S02, S03...), rode um script GraphQL (reaproveitando o que já foi feito na Parte 1) que exporte os itens do Project e seu status atual para um arquivo CSV. Esses snapshots, acumulados sprint a sprint, serão a base de dados dos Labs 04 e 05 — como o GitHub Projects não guarda histórico de mudanças de coluna consultável via API, essa série de snapshots faz esse papel.
7. **Referencie o número da Issue em cada commit** (ex.: `#12 implementa consulta GraphQL`), para que o GitHub vincule automaticamente commit ↔ Issue no histórico. **A correção do professor é feita a partir do board**: commits sem essa referência não serão considerados na avaliação, mesmo que estejam no repositório.

O board do grupo, a política de WIP e o script de snapshot estão documentados em
[`kanban/README.md`](../kanban/README.md).

## Relatório Final

Documento com: (i) introdução com hipóteses informais sobre as RQs; (ii) metodologia de coleta; (iii) resultados por RQ (valores medianos, contagem por categoria quando aplicável); (iv) discussão hipótese vs. resultado; (v) uma seção "Configuração do processo", descrevendo a estrutura do GitHub Projects (colunas, política de WIP) e um print do board ao final do laboratório, com o link do repositório/GitHub Projects do grupo.

## Processo de Desenvolvimento

**Lab01S01** (4 pontos): Consulta GraphQL para 100 repositórios (todos os dados/métricas necessários) + requisição automática + GitHub Projects criado, com colunas (Status) e limite de WIP definidos e primeiras Issues em uso.

*Divisão sugerida por integrante (desde esta sprint, para viabilizar desenvolvimento individual semanal em um trio):* distribua as RQs em 3 partes, uma por integrante (ex.: A → RQ01+RQ02; B → RQ03+RQ04; C → RQ05+RQ06+bônus). Cada integrante implementa e testa, em Issue própria, a extração e uma validação rápida (numa amostra de 5-10 repositórios) dos campos/métricas da sua parte, antes de integrar ao script único de consulta do grupo.

**Lab01S02** (4 pontos): Paginação (consulta 1000 repositórios) + dados em .csv + primeira versão do relatório com hipóteses informais + board atualizado e primeiro snapshot exportado, refletindo o fluxo real de trabalho do grupo em S01 e S02.

*Divisão sugerida por integrante:* a paginação em si (tarefa mecânica) pode ficar com qualquer integrante, mas cada integrante deve validar individualmente, para a sua parte de RQs, a consistência dos dados nos 1000 repositórios (distribuição, outliers, valores ausentes) e escrever, em Issue própria, a hipótese informal correspondente.

**Lab01S03** (4 pontos): Análise e visualização de dados para as 6 RQs (+ bônus).

**Relatório Final** (3 pontos): elaboração do documento final (ver seção "Relatório Final" acima), incluindo o anexo com print do board mostrando o fluxo completo do Lab01 e a política de WIP em uso.

**Prazo final:** conforme cronograma da disciplina.
**Valor total:** 15 pontos | Desconto de 1,0 ponto por dia de atraso | Desconto de até 10% da nota da sprint por qualidade insuficiente do uso do GitHub Projects (WIP não respeitado, Issues sem Assignee, cartões desatualizados, ausência de evolução semanal).
**Observação:** não é permitido o uso de bibliotecas de terceiros que consultem a API do GitHub — a query GraphQL deve ser escrita e consumida por script próprio do grupo. A correção é feita a partir do GitHub Projects: commits sem referência ao número da Issue correspondente não serão considerados.

---

## Execução dos scripts de mineração

### 1. Coleta de dados

Os resultados das validações individuais (5-10 repositórios, uma por integrante, antes de integrar
ao script único) são salvos em `lab01/data/amostra/`. Use `--n` para definir a quantidade:

```bash
python lab01/src/collection/collect_sample_rq01_rq02.py --n 10 --out lab01/data/amostra/rq01_rq02_10.csv
python lab01/src/collection/collect_sample_rq03_rq04.py --n 10 --out lab01/data/amostra/rq03_rq04_10.csv
python lab01/src/collection/collect_sample_rq05_rq06.py --n 10 --out lab01/data/amostra/rq05_rq06_10.csv
```

Esses três scripts não são usados para gerar os dados finais (100 ou 1000 repositórios) — essa etapa
é só validação individual. A partir daí, toda coleta e análise usa o script consolidado, que coleta
todas as RQs de uma vez em
`lab01/data/sprint_s01/all_rqs.csv`:
```bash
python lab01/src/collection/collect_all_rqs.py --n 100
```

### 2. Análise da RQ03

Sem coleta nova: cruza a idade do repositório (RQ01) com o total de releases (RQ03), lendo direto de
`lab01/data/sprint_s01/all_rqs.csv` (o CSV consolidado do passo 1, único ponto de entrada — evita que
essa análise e a coleta bruta fiquem lendo de coletas diferentes e divergindo entre si).

```bash
python lab01/src/analysis/analyze_rq03.py
```

Faz duas coisas que o total bruto de releases não responde sozinho:

1. **Releases por ano** (`releases / age_years`) como métrica principal — o total acumulado favorece
   repositório antigo, e a normalização corrige isso. O total bruto continua no CSV como métrica
   secundária.
2. **Separa os repositórios sem release.** São 40 dos 100, e incluí-los ou não muda a mediana de
   136,5 para 15 (ou de 22,2 para 5,8 releases por ano). O script reporta os dois recortes com
   mediana, quartis e média, mostra o percentual de repositórios sem release por linguagem e lista
   os maiores para classificação manual no relatório — entre eles estão `torvalds/linux` e
   `golang/go`, que versionam por tag em vez de publicar em *GitHub Releases*.

Saídas: `lab01/data/sprint_s01/rq03_releases_por_ano.csv` (por repositório, com a coluna
`sem_release`) e `lab01/data/sprint_s01/rq03_resumo.csv` (o comparativo com e sem os zeros).

### 3. Análise da RQ07 (bônus)

A RQ07 não faz coleta nova: ela cruza, por repositório, a linguagem primária (RQ05) com as métricas
das RQ02, RQ03 e RQ04, lendo do mesmo `all_rqs.csv` consolidado. Rode depois de ter o CSV do passo 1:

```bash
python lab01/src/analysis/analyze_rq07.py
```

Saídas em `lab01/data/sprint_s01/`: `rq07_por_linguagem.csv` (mediana das três métricas por
linguagem) e `rq07_top_vs_demais.csv` (linguagens mais populares vs. demais). O caminho de entrada
pode ser trocado com `--entrada` (ex.: para rodar sobre os 1000 repositórios do Lab01S02).

**Fonte de "linguagens mais populares":** [GitHub Octoverse 2024](https://github.blog/news-insights/octoverse/octoverse-2024/),
top 10 linguagens por número de desenvolvedores — Python, JavaScript, TypeScript, Java, C#, C++, PHP,
Shell, C e Go. É a mesma referência usada na RQ05 e está na constante `TOP_LANGUAGES` do script.
Repositórios sem linguagem primária (`N/A`) formam um terceiro grupo, separado das "demais
linguagens": eles não são um contraexemplo de linguagem impopular, são um caso à parte (listas,
documentação) e misturá-los com as demais puxaria as medianas para baixo.

### 4. Extra — idade explica o número de estrelas?

Não faz parte das RQs obrigatórias. Surgiu de uma dúvida ao olhar os dados da RQ01: se sistemas
populares tendem a ser antigos, os mais antigos deveriam ser também os mais estrelados.

```bash
python lab01/src/analysis/extra_idade_vs_popularidade.py
```

Nos 100 repositórios, **não deveriam**: a correlação entre idade e estrelas é 0,112 (Pearson) e
0,003 (Spearman) — ou seja, praticamente nenhuma. Quebrando por faixa etária, a faixa com **menos de
1 ano de vida tem a maior mediana de estrelas de todas** (195.075, contra 172.660 dos repositórios
com mais de 10 anos). São 11 repositórios com menos de um ano na lista dos 100 mais estrelados do
GitHub, quase todos ligados a IA e a ferramentas de agentes (`openclaw/openclaw` com 386k estrelas
em 8 meses, `anthropics/skills`, `ultraworkers/claw-code`).

A leitura para o relatório: a RQ01 responde que a *mediana* de idade é alta (8,3 anos), mas idade não
é o que produz estrelas. Convivem duas populações diferentes na mesma lista — projetos maduros que
acumularam estrelas ao longo de uma década e projetos virais recentes que chegaram lá em meses.
A métrica de idade sozinha esconde esse segundo grupo.

Saídas em `lab01/data/sprint_s01/`: `extra_idade_por_faixa.csv` e `extra_repos_jovens.csv`
(controlado por `--listar`, padrão 10).

## Métricas por RQ

| RQ | Métrica | Campo GraphQL | Coluna no CSV |
|---|---|---|---|
| RQ01 | idade do repositório | `createdAt` | `age_years` |
| RQ02 | total de pull requests aceitas | `pullRequests(states: MERGED).totalCount` | `merged_pull_requests` |
| RQ03 | total de releases | `releases(orderBy: CREATED_AT).totalCount` | `releases` |
| RQ04 | tempo até a última atualização | `pushedAt` | `days_since_last_push` |
| RQ05 | linguagem primária | `primaryLanguage.name` | `primary_language` |
| RQ06 | razão issues fechadas / total | `issues.totalCount` e `issues(states: CLOSED).totalCount` | `closed_issues_ratio` |
| RQ07 | RQ02/RQ03/RQ04 por linguagem | cruzamento dos CSVs acima (sem coleta nova) | `mediana_prs_aceitas`, `mediana_releases`, `mediana_dias_sem_push` |

Métricas derivadas, calculadas a partir das acima e usadas no relatório:

| RQ | Métrica derivada | Cálculo | Coluna no CSV |
|---|---|---|---|
| RQ03 | releases por ano | `releases / age_years` | `releases_por_ano` |
| RQ03 | repositório sem release | `releases == 0` | `sem_release` |

## Limitações conhecidas da coleta

1. **O `orderBy` em `releases` é obrigatório.** Sem ele a API trunca `totalCount` em 1000:
   `vercel/next.js` retornava 1000 no lugar de 3800 e `ggml-org/llama.cpp`, 1000 no lugar de 6855.
   Com `orderBy: {field: CREATED_AT, direction: DESC}` os 100 valores conferem com a API REST.
   O erro é traiçoeiro porque repositórios com menos de 1000 releases dão o mesmo resultado das duas
   formas (`kubernetes/kubernetes`: 810), então só aparece nos maiores. Os scripts avisam se algum
   repositório vier com exatamente 1000 releases, que é o sintoma da remoção acidental do `orderBy`.
   **Isso não afeta RQ02 nem RQ06**: `pullRequests` e `issues` não truncam (no `kubernetes`, sem
   nenhum `orderBy`, retornam 65.645 e 49.518).
2. **`primary_language` usa a string `"N/A"`** quando o repositório não tem linguagem primária (mesma
   convenção do script de RQ05/RQ06). O pandas lê `"N/A"` como `NaN` por padrão e o `groupby` descarta
   essas linhas em silêncio — são 13 dos 100 repositórios. Ao analisar, leia com
   `pd.read_csv(..., keep_default_na=False)`.
3. **Paginação adaptativa.** A API pode responder 502/503/504 quando a página é cara demais —
   acontecia na faixa 76-100, que junta `kubernetes`, `electron` e `llama.cpp`. A paginação começa
   com páginas de 25 e reduz pela metade até a API aceitar, então o número de requisições varia entre
   execuções. Com o `orderBy` do item 1 a consulta ficou mais barata e as páginas de 25 passaram a ser
   aceitas, mas a redução automática continua como proteção para os 1000 repositórios do Lab01S02.
   Essa lógica (retry + redução de página + pausa quando o rate limit está acabando) mora só em
   `src/collection/graphql_pagination.py`, compartilhada por `collect_all_rqs.py` e
   `collect_sample_rq03_rq04.py` — os dois únicos scripts que paginam sobre mais de uma página de
   resultado. Ela tinha sido implementada em duplicidade nos dois scripts, com pequenas diferenças
   entre si; unificar evita que um dos dois fique sem a correção quando um bug de paginação aparecer.
4. **RQ03 e RQ07 leem de um único CSV consolidado (`all_rqs.csv`).** Os scripts de coleta por dupla de
   RQ (`collect_sample_rq01_rq02.py`, `collect_sample_rq03_rq04.py`, `collect_sample_rq05_rq06.py`)
   existem só para a validação individual de 5-10 repositórios de cada integrante (ver
   [`data/README.md`](data/README.md)) — a partir daí, toda análise usa o `all_rqs.csv` gerado por
   `collect_all_rqs.py`. Antes disso, `analyze_rq03.py` e `analyze_rq07.py` liam cada um dos CSVs por
   dupla de RQ separadamente, o que fazia os números divergirem do `all_rqs.csv` porque vinham de
   coletas em momentos diferentes (releases novas apareciam entre uma coleta e outra). Ler de uma
   fonte só elimina essa divergência.
5. **Mediana por linguagem só é interpretável com repositórios suficientes.** Nos 100 repositórios,
   Java, C# e Dart aparecem uma única vez cada — a "mediana" ali é o próprio repositório. Por isso a
   resposta da RQ07 sai da tabela agrupada (top-10 vs. demais), e a tabela por linguagem traz a
   coluna `repos` para deixar esse limite explícito. Com os 1000 do Lab01S02 o problema diminui, mas
   não desaparece na cauda.
6. **As contagens variam entre execuções.** São métricas vivas: rodar `collect_all_rqs.py` de novo
   pode trazer releases novas nos mesmos repositórios (ex.: `vercel/next.js` 3799 → 3800 entre duas
   coletas). Pequenas diferenças entre execuções são esperadas; diferenças grandes, ou um valor
   exatamente 1000 em `releases`, indicam problema de query (ver item 1).

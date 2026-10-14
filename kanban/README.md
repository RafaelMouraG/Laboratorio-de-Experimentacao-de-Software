# Kanban do grupo

Cada laboratório tem o seu board no GitHub Projects (v2). O script de exportação e os snapshots
servem para todos eles, por isso moram na raiz do repositório e não dentro de um `labXX/`.

## Identificação dos Projects

| Lab | URL | Número | ID |
|---|---|---|---|
| Lab01 | https://github.com/users/RafaelMouraG/projects/6 | `6` | `PVT_kwHOBl12sM4BgDN4` |
| Lab02 | https://github.com/users/RafaelMouraG/projects/7 | `7` | `PVT_kwHOBl12sM4Bi3ar` |
| Lab03 | https://github.com/users/RafaelMouraG/projects/10 | `10` | `PVT_kwHOBl12sM4Bl2H9` |

Todos são do usuário `RafaelMouraG` (não é organização).

O dono ser um **usuário** importa para a query: o campo raiz é `user(login:)`, não
`organization(login:)`.

## Colunas do board

O campo `Status` (single select) tem as cinco colunas exigidas pelo enunciado:

`Backlog` → `To Do` → `Doing` → `Review` → `Done`

**Limite de WIP em Doing: 3** — um cartão em andamento por integrante do trio. Passar disso
significaria que alguém está com duas frentes abertas ao mesmo tempo, e como cada RQ é desenvolvida
individualmente dentro da própria Issue, o gargalo real do grupo é pessoa, não tarefa
(item 4 da Parte 2 do [enunciado do Lab01](../lab01/README.md)).

Todo cartão é uma Issue de verdade do repositório, com Assignee — nada de draft issue solta, para
que tudo seja rastreável pela API.

## Snapshot de fechamento de sprint

O GitHub Projects **não guarda histórico de mudança de coluna consultável via API**: a API só
devolve onde cada cartão está agora. Rodando o export ao fim de cada sprint, a série de CSVs
acumulada em `snapshots/` passa a fazer esse papel e vira a base de dados dos **Labs 04 e 05**.

Por isso o snapshot é tirado **no fechamento da sprint, com o board refletindo o trabalho real** —
mover cartão retroativamente na véspera destrói justamente o dado que esses labs vão analisar.

### Como rodar

Da raiz do repositório, com o ambiente virtual ativo (ver [README da raiz](../README.md)):

```bash
python kanban/export_snapshot.py --sprint S01
```

O `GITHUB_TOKEN` do `.env` precisa do escopo `read:project`.

| Argumento | Padrão | Uso |
|---|---|---|
| `--login` | `RafaelMouraG` | dono do Project |
| `--number` | `6` | número do ProjectV2 (`10` no Lab03) |
| `--milestone` | todos | exporta só as issues desse milestone |
| `--sprint` | `S01` | rótulo gravado na coluna `sprint` do CSV |
| `--out` | `kanban/snapshots/snapshot_sprint_01.csv` | arquivo de saída |

A cada sprint mudam os dois juntos — foi assim que saiu a última:
`--sprint S03 --out kanban/snapshots/snapshot_sprint_03.csv`.
Um arquivo por sprint, todos versionados — é o acúmulo que forma a série histórica.

No Lab03 a sprint seguinte começa antes da anterior ser fotografada, então o board tem issues de
duas sprints ao mesmo tempo. O `--milestone` separa:

```bash
python kanban/export_snapshot.py --number 10 --milestone "Lab03 - Sprint 1" --sprint S01 \
  --out kanban/snapshots/lab03_sprint_01.csv
```

### Formato do CSV

| Coluna | Conteúdo |
|---|---|
| `snapshot_date` | data UTC da exportação (`YYYY-MM-DD`) |
| `sprint` | rótulo passado em `--sprint` |
| `issue` | número da Issue no repositório |
| `titulo` | título do cartão |
| `status` | coluna do board no momento do snapshot |
| `assignee` | logins dos responsáveis, separados por `;` |
| `state` | `OPEN` ou `CLOSED` |
| `url` | link da Issue |

As linhas saem ordenadas pela ordem das colunas do board e depois pelo número da Issue, para o
`git diff` entre snapshots ficar legível.

Casos de borda tratados pelo script: cartão sem coluna vira `Sem Status`; item cujo conteúdo o token
não enxerga é ignorado; draft issue e pull request entram no CSV com `issue` vazio, para não sumir
do snapshot. Uma coluna nova no board é exportada normalmente, mas o script avisa no fim da execução
para acrescentá-la à constante `ORDEM_STATUS` e manter a ordenação correta.

## Snapshots

| Arquivo | Sprint | Data | Itens |
|---|---|---|---|
| `snapshots/snapshot_sprint_01.csv` | S01 | 14/08/2026 | 12 |
| `snapshots/snapshot_sprint_02.csv` | S02 | 20/08/2026 | 31 |
| `snapshots/snapshot_sprint_03.csv` | S03 | 27/08/2026 | 33 |
| `snapshots/lab03_sprint_01.csv` | Lab03 S01 | 14/10/2026 | 13 |

A distribuição por coluna de cada snapshot sai do próprio CSV — o script imprime o resumo ao final
da execução.

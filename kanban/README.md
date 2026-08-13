# Kanban do grupo

O quadro do grupo no GitHub Projects (v2) acompanha todos os laboratórios do semestre, por isso mora
na raiz do repositório e não dentro de `lab01/`.

## Identificação do Project

| | |
|---|---|
| Título | Laboratório de Experimentação de Software |
| URL | https://github.com/users/RafaelMouraG/projects/6 |
| Dono | usuário `RafaelMouraG` (não é organização) |
| Número | `6` |
| ID | `PVT_kwHOBl12sM4BgDN4` |

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
| `--number` | `6` | número do ProjectV2 |
| `--sprint` | `S01` | rótulo gravado na coluna `sprint` do CSV |
| `--out` | `kanban/snapshots/snapshot_sprint_01.csv` | arquivo de saída |

Nas próximas sprints, mude os dois: `--sprint S02 --out kanban/snapshots/snapshot_sprint_02.csv`.
Um arquivo por sprint, todos versionados — é o acúmulo que forma a série histórica.

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
| `snapshots/snapshot_sprint_01.csv` | S01 | 13/08/2026 | 11 |

A distribuição por coluna de cada snapshot sai do próprio CSV — o script imprime o resumo ao final
da execução.

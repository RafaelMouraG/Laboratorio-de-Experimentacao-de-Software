# Relatório Lab01

## 1. Introdução

Este documento consolida a primeira etapa do laboratório para analisar os 1.000 repositórios mais populares do GitHub. Abaixo estão as hipóteses informais escritas pelos integrantes para as seis RQs do projeto:

- **RQ01:** Repositórios populares devem ser majoritariamente maduros, mas com uma cauda de projetos recentes que viralizaram rápido, como já apontava a análise extra dos 100, onde a faixa com menos de 1 ano tinha a maior mediana de estrelas. A mediana de idade seguir próxima entre 100 e 1000 repositórios (8,3 → 7,7 anos) é consistente com essa hipótese de duas populações.
- **RQ02:** Espera-se volume alto de PRs aceitas na mediana, mas a métrica tem viés conhecido: projetos que não usam PR do GitHub como fluxo principal aparecem com zero, o que não significa baixa contribuição externa.
- **RQ03:** Espera-se que sistemas populares lancem releases com frequência, mas a métrica deve ser bimodal em vez de ter um valor típico único: um grupo grande não usa *GitHub Releases* de jeito nenhum (27,5% nos 1.000), ou porque não é software, ou porque versiona por tag, como `torvalds/linux` e `golang/go`. Entre os que usam, a cadência deve ser alta. A validação é consistente com isso: nenhuma release em um quarto da amostra e ~15 releases por ano na mediana dos 725 que publicam. Por isso a resposta sai de `releases_por_ano` com os dois recortes declarados, e não do total bruto, que favorece repositório antigo.
- **RQ04:** Espera-se que sistemas populares sejam atualizados com muita frequência, com mediana de poucos dias desde o último push, com uma cauda de projetos arquivados que continuam estrelados por reputação acumulada (`atom/atom`, `adobe/brackets`). Mediana de 3 dias e 11,4% parados há mais de um ano sustentam as duas partes. A hipótese só é testável com `pushedAt`: por `updatedAt` a mediana cai para 43 minutos e a cauda de abandonados desaparece do gráfico.
- **RQ05:** Espera-se que os projetos de maior sucesso sejam desenvolvidos predominantemente nas linguagens que dominam o mercado (tendo como referência o TIOBE Index Oficial). A justificativa é estrutural: linguagens populares oferecem os maiores ecossistemas de bibliotecas e uma vasta massa de desenvolvedores aptos a contribuir.
- **RQ06:** Espera-se encontrar uma altíssima taxa de issues fechadas (mediana > 80%). A saúde de um grande projeto open-source depende da manutenção ativa; uma alta taxa de resolução comprova que os mantenedores engajam com a comunidade e não deixam bugs se acumularem, o que é vital para manter a popularidade.

## 2. Metodologia

A coleta utiliza a API GraphQL do GitHub. A query usa o filtro `search(type: REPOSITORY)` integrado com paginação em cursores (`after`) para extrair os 1.000 repositórios com maior quantidade de estrelas.

### Limitações conhecidas da coleta

Algumas particularidades dos dados já foram mapeadas nas amostras iniciais e são tratadas na análise:

- **Fonte de "Linguagens Mais Populares" (RQ05):** Fixamos como fonte oficial o [TIOBE Index Oficial](https://www.tiobe.com/tiobe-index/), mantendo a mesma referência ao longo de todo o laboratório.
- **Taxa de Pull Requests Fechados (RQ02):** A API conta os PRs integrados de qualquer autor na métrica `merged_pull_requests`. Ela não diferencia a contribuição do core team da contribuição de um desenvolvedor externo.
- **Linguagem Principal "N/A" (RQ05):** Alguns projetos não têm a linguagem preenchida. Para que o Pandas não os descarte como dados faltantes, é obrigatório ler o CSV com `keep_default_na=False`.
- **`pushedAt` vs `updatedAt` (RQ04):** Adotamos a data do último envio (`pushedAt`) porque o campo `updatedAt` sofre alteração com qualquer mudança básica (receber estrela, mudar label) e mascara repositórios já abandonados.
- **Ausência de Releases (RQ03):** Listas, tutoriais e livros não são software e não costumam abrir *Releases*, o que puxa o total de repositórios com "zero releases" para cima.
- **Repositórios sem Issues (RQ06):** Repositórios com `total_issues == 0` costumam gerar a taxa enganosa de `0.0`. Eles precisam ser desconsiderados do cálculo para não jogarem a mediana de fechamento para baixo.

## 3. Resultados

### RQ01: Idade dos repositórios

Nos 1.000 repositórios coletados, a idade mediana é de **7,72 anos** (Q1 3,51, Q3 11,34, mínimo
0,01, máximo 18,35). O histograma (`lab01/relatorio/figuras/rq01_histograma_idade.png`) confirma a
cauda de projetos recentes prevista na hipótese: 81 dos 1.000 repositórios (8,1%) têm menos de um
ano de vida, contra 345 (34,5%) com mais de dez anos. A distribuição por faixa etária
(`lab01/relatorio/figuras/rq01_faixas_idade.png`) é:

| Faixa | Repositórios | % de 1.000 |
|---|---|---|
| < 1 ano | 81 | 8,1% |
| 1-3 anos | 109 | 10,9% |
| 3-5 anos | 133 | 13,3% |
| 5-10 anos | 332 | 33,2% |
| > 10 anos | 345 | 34,5% |

### RQ02: Pull requests aceitas

Nos 1.000 repositórios, 20 (2%) têm **zero pull requests aceitas** (recorte declarado, não dado
ausente): são projetos como `torvalds/linux` que aceitam contribuição fora do fluxo de PR do GitHub
(patch por lista de e-mail), então zero não significa baixa contribuição externa. A métrica
`merged_pull_requests` também não distingue autor externo de membro do core team: a API não expõe
essa informação por PR agregado.

Considerando todos os 1.000 repositórios, a mediana é de **765,5 PRs aceitas** (Q1 175, Q3 3.390);
excluindo os 20 com zero, a mediana sobe para **811 PRs aceitas** (Q1 191,75, Q3 3.485,25), com
diferença pequena porque os zeros são só 2% da amostra. O histograma em escala log
(`lab01/relatorio/figuras/rq02_histograma_prs_log.png`) mostra volume alto na mediana com cauda
longa nos dois sentidos; o boxplot em escala log
(`lab01/relatorio/figuras/rq02_boxplot_prs.png`, sem os zeros) evidencia os outliers acima de ~8 mil
PRs aceitas.

### RQ03: Releases

A distribuição de releases é bimodal, então a RQ03 não tem um valor típico único. Dos 1.000
repositórios, **275 (27,5%) não publicam nenhuma release** e 725 publicam
(`lab01/relatorio/figuras/rq03_com_vs_sem_release.png`). Esse recorte encolheu conforme a amostra
cresceu: eram **40 dos 100 repositórios da S01 (40%)** e são **27,5% nos 1.000**, então o
percentual só tem leitura junto com o tamanho da amostra sobre o qual foi medido. A queda não é
inconsistência de coleta: quanto mais alto o corte de popularidade, maior a concentração de
repositório de conteúdo (listas *awesome*, livros, roadmaps), que não publica release por não ser
software; a cauda dos 1.000 traz proporcionalmente mais biblioteca e ferramenta, que publica.

Pela métrica principal, `releases_por_ano`, a mediana é de **6,78 releases por ano** considerando
todos os 1.000 repositórios e de **14,94** entre os 725 que publicam (Q1 4,91, Q3 38,24). Os dois
recortes valem juntos e respondem a perguntas diferentes: o primeiro dá a cadência do repositório
popular médio, incluindo quem nunca publica; o segundo, a cadência de quem usa *GitHub Releases*. O
histograma em escala log (`lab01/relatorio/figuras/rq03_histograma_releases_por_ano.png`, apenas os
725 que publicam) mostra a massa concentrada entre uma e algumas dezenas de releases por ano, com
cauda longa até 2.214 releases por ano; a escala log é necessária porque a cadência vai de 0,06 a
esse extremo.

O **total de releases é métrica secundária** (mediana 40,5 com todos, 95,0 entre os que publicam)
porque mede tempo de vida acumulado, não frequência: entre os 725 que publicam, a mediana de
`releases` sobe de 60,5 nos repositórios com menos de 5 anos para 106,5 nos com mais de 10, enquanto
a cadência cai de 30,8 para 8,34 releases por ano no mesmo sentido. O acumulado premia o repositório
antigo, onde a frequência é menor, e por isso a resposta da RQ03 sai de `releases_por_ano`.

A ausência de release se concentra por linguagem
(`lab01/relatorio/figuras/rq03_sem_release_por_linguagem.png`). Entre as 14 linguagens com pelo
menos 10 repositórios na amostra, o percentual sem release vai de 90,9% em HTML a 5,3% em Go e Rust:

| Linguagem | Repositórios | Sem release | % sem release |
|---|---|---|---|
| HTML | 11 | 10 | 90,9% |
| Jupyter Notebook | 24 | 21 | 87,5% |
| `N/A` | 87 | 74 | 85,1% |
| Shell | 20 | 8 | 40,0% |
| Ruby | 13 | 4 | 30,8% |
| C | 21 | 6 | 28,6% |
| JavaScript | 110 | 31 | 28,2% |
| Python | 229 | 60 | 26,2% |
| Java | 41 | 9 | 22,0% |
| C++ | 40 | 6 | 15,0% |
| Swift | 10 | 1 | 10,0% |
| TypeScript | 174 | 14 | 8,0% |
| Go | 76 | 4 | 5,3% |
| Rust | 57 | 3 | 5,3% |

O corte de 10 repositórios evita que uma linguagem com um único projeto sem release apareça como
barra de 100%. O gradiente é de conteúdo contra software, não de disciplina de release entre
comunidades: HTML, Jupyter Notebook e `N/A` concentram material que não é software, enquanto Go e
Rust são quase só biblioteca e ferramenta, com versionamento publicado. O grupo sem release ainda
inclui software que versiona por tag em vez de publicar em *GitHub Releases*, como `torvalds/linux`
e `golang/go`: zero release não significa ausência de versionamento.

### RQ04: Frequência de atualização

Os 1.000 repositórios são atualizados com frequência alta na maior parte da amostra: a mediana é de
**3,02 dias desde o último push** (Q1 0,45, Q3 52,1). A curva acumulada
(`lab01/relatorio/figuras/rq04_curva_acumulada_push.png`) detalha o ritmo:

| Último push até | Repositórios | % acumulado |
|---|---|---|
| 1 dia | 325 | 32,5% |
| 7 dias | 606 | **60,6%** |
| 30 dias | 720 | **72,0%** |
| 90 dias | 789 | 78,9% |
| 180 dias | 837 | 83,7% |
| 365 dias | 886 | 88,6% |
| 730 dias | 934 | 93,4% |

Quase um terço da amostra recebeu push nas últimas 24 horas e **60,6% na última semana**, o que
sustenta a primeira metade da hipótese. A segunda metade está no que a curva **não** cobre: ela para
em 93,4%, e o que falta para 100% é a cauda de projetos abandonados. São **114 repositórios (11,4%)
sem push há mais de um ano** e 66 (6,6%) há mais de dois anos; o extremo é
`exacity/deeplearningbook-chinese`, parado há 2.448 dias com 37 mil estrelas. A cauda aparece
destacada à direita no histograma em escala log
(`lab01/relatorio/figuras/rq04_histograma_dias_push_log.png`), com um agrupamento visível entre 700
e 1.000 dias que reúne projetos como `atom/atom` (1.321 dias, 60,8 mil estrelas) e `adobe/brackets`
(1.526 dias, 33 mil estrelas), editores descontinuados que seguem estrelados por reputação
acumulada, não por atividade. A escala log é necessária porque a métrica cobre mais de cinco ordens
de grandeza, de 0,01 a 2.448 dias; os 18 repositórios com 0,0 dia (push no momento da coleta) ficam
fora do histograma, porque log(0) é indefinido.

**A métrica é `pushedAt`, não `updatedAt`**, e a escolha decide o resultado da RQ04. `updatedAt` muda
com qualquer alteração no repositório (receber estrela, mudar label, editar a descrição) e não só
com desenvolvimento. Medido nos mesmos 1.000: 921 têm `updatedAt` mais recente que `pushedAt`, 280
divergem em mais de 30 dias, e a mediana cairia de 3,02 dias para **0,03 dia (cerca de 43 minutos)**.
O efeito decisivo é sobre a cauda: por `pushedAt` são 114 repositórios parados há mais de um ano, e
por `updatedAt` seriam **zero**: `updatedAt` faria todo repositório da lista parecer ativo hoje,
inclusive os abandonados, e apagaria a metade da hipótese que o gráfico precisa mostrar.
`days_since_last_update` fica no CSV apenas como material dessa comparação.

### RQ05: Linguagens mais populares

Nos 1.000 repositórios coletados, a linguagem Python lidera com 229 repositórios (22,9%), seguida por TypeScript com 174 (17,4%) e Rust com 57 (5,7%). Agrupando pela popularidade no mercado (tendo como referência o TIOBE Index), pouco mais da metade da amostra, 506 repositórios (50,6%), utiliza alguma das linguagens do Top 10 do TIOBE. O restante divide-se entre 407 repositórios (40,7%) em outras linguagens fora do Top 10 e 87 repositórios (8,7%) sem linguagem primária preenchida ("N/A"). A categoria "N/A" aparece isolada no gráfico (`lab01/relatorio/figuras/rq05_top15_linguagens.png`), não sendo somada às "demais", para manter a transparência dos dados.

### RQ06: Issues fechadas

Dos 1.000 repositórios coletados, **957 entraram no cálculo**: os 43 com `total_issues == 0` foram
excluídos porque a coleta grava `closed_issues_ratio = 0.0` nesses casos (não são projetos com 0
fechadas, são projetos que não registram issues no GitHub); incluí-los criaria uma taxa falsamente
baixa e derrubaria a mediana. Com o recorte válido, a mediana de fechamento é de **87,5%** (Q1
70,49%, Q3 96,77%), acima dos 80% que a hipótese informal esperava. O histograma
(`lab01/relatorio/figuras/rq06_histograma_ratio.png`) mostra a concentração em taxas altas, com 430
repositórios (44,9%) acima de 90%; o boxplot (`lab01/relatorio/figuras/rq06_boxplot_ratio.png`)
reforça a mesma leitura. Na faixa:

| Faixa | Repositórios | % de 957 |
|---|---|---|
| < 50% | 108 | 11,3% |
| 50-75% | 171 | 17,9% |
| 75-90% | 248 | 25,9% |
| > 90% | 430 | 44,9% |

## 4. Discussão (Hipótese vs Resultado)

### RQ01: Idade dos repositórios

**Hipótese:** repositórios populares são majoritariamente maduros, mas com uma cauda de projetos
recentes que viralizaram rápido. A mediana seguir próxima entre 100 e 1.000 (8,3 → 7,7 anos).

**Resultado:** mediana de **7,72 anos** (Q1 3,51, Q3 11,34), 345 repositórios (34,5%) com dez anos
ou mais e 81 (8,1%) com menos de um ano.

**Veredito: confirmada.** A hipótese de duas populações se mantém: a mediana mal se moveu
(8,3 → 7,7) porque a cauda jovem (projetos virais recentes como `open-webui/open-webui` e
`anthropics/claude-code`) compensa a cauda madura trazida pelos 1.000. O que a amostra de 1.000
mostra e a de 100 não: a cauda jovem não é ruído, é uma fração estável da amostra (8,1%); os
projetos mais velhos do topo são majoritariamente conteúdo (listas, livros, tutoriais), não
software maduro em manutenção ativa.

### RQ02: Pull requests aceitas

**Hipótese:** volume alto de PRs aceitas na mediana, mas com viés conhecido: projetos que não usam
PR do GitHub como fluxo principal aparecem com zero.

**Resultado:** mediana de **765,5 PRs aceitas** (Q1 175, Q3 3.390); 20 repositórios (2%) com zero.

**Veredito: confirmada.** Volume alto na mediana e o viés do zero se confirma nos casos mais
extremos: `torvalds/linux` e `FFmpeg/FFmpeg`, os projetos mais populares da amostra, integram
contribuição por e-mail/patch, fora do fluxo de PR, e por isso aparecem com zero. A divergência
numérica (mediana de 1.253,5 na amostra de 100 para 765,5 nos 1.000) é esperada: a cauda dos 1.000
traz proporcionalmente mais bibliotecas e ferramentas de porte médio. O que a amostra de 1.000
mostra e a de 100 não: o sintoma "projeto gigante com zero PR" só fica evidente com a escala; na
amostra de 100 os zeros eram poucos e genéricos, sem o padrão claro de "não usa o fluxo de PR do
GitHub".

### RQ03: Releases

**Hipótese:** cadência alta de releases, mas métrica bimodal: um grupo grande não usa *GitHub
Releases* (27,5% nos 1.000) por não ser software ou versionar por tag; entre os que publicam, a
cadência é alta.

**Resultado:** 275 repositórios (27,5%) sem release; entre os 725 que publicam, mediana de
**14,94 releases/ano** (6,78 considerando todos).

**Veredito: confirmada, com recorte reinterpretado.** A bimodalidade se sustenta nos dois extremos:
27,5% sem nenhuma release e mediana de ~15 releases/ano entre os que publicam.

**Divergência explicada (40% → 27,5%):** a queda de 12,5 p.p. entre as amostras não é
inconsistência de coleta. Quanto mais alto o corte de popularidade, maior a concentração de
repositório de conteúdo (listas *awesome*, livros, roadmaps), que não publica release por não ser
software; os maiores sem release nos 1.000 são esses (`codecrafters-io/build-your-own-x`,
`sindresorhus/awesome`, `EbookFoundation/free-programming-books`). A cauda dos 1.000 traz
proporcionalmente mais biblioteca e ferramenta, que publica, e por isso o percentual cai. A
consequência para o relatório: 27,5% não é uma constante dos "repositórios populares", é sensível ao
corte de popularidade, e qualquer citação precisa do tamanho da amostra ao lado. O recorte "sem
release" continua válido e muda a resposta da RQ (mediana de 95 → 40,5 releases totais; 14,94 →
6,78 por ano), só não pode ser apresentado como valor estável.

### RQ04: Atualização

**Hipótese:** push frequente (mediana de poucos dias) convivendo com cauda de projetos arquivados
que seguem estrelados por reputação acumulada.

**Resultado:** mediana de **3,02 dias** desde o último push, 60,6% com push na última semana e 11,4%
parados há mais de um ano.

**Veredito: confirmada.** As duas partes da hipótese aparecem nos 1.000. A divergência numérica com
a amostra de 100 (mediana de ~0,5 dia) se explica pela cauda: os 1.000 trazem os arquivados
(`atom/atom`, `adobe/brackets`) que o topo de 100 escondia. O que a amostra de 1.000 mostra e a de
100 não: o viés de `updatedAt` (921 dos 1.000 repositórios têm `updatedAt` mais recente que
`pushedAt`, com mediana de 43 minutos contra 3,02 dias), porque o campo muda com star, label e
edição de descrição. Por `updatedAt` a cauda de abandonados desapareceria por completo do gráfico; a
hipótese só é testável com `pushedAt`.

### RQ05: Linguagens populares

**Hipótese:** os projetos de maior sucesso são desenvolvidos predominantemente nas linguagens que
dominam o mercado (referência: TIOBE Index), por oferecerem os maiores ecossistemas de bibliotecas
e a maior massa de contribuidores.

**Resultado:** 506 repositórios (50,6%) usam linguagem do top 10 do TIOBE; Python lidera (229),
seguido de TypeScript (174) e JavaScript (110). Java (41) e C++ (40), tradicionais gigantes de
mercado, aparecem abaixo de Go (76) e Rust (57); 87 repositórios (8,7%) vêm sem linguagem primária
("N/A").

**Veredito: parcialmente confirmada.** A concentração existe, mas não nas linguagens que o TIOBE
sugere: a amostra é dominada pelo ecossistema de dados e web (Python/TypeScript/JavaScript somam
51,3%), enquanto Java e C++ (top 3 de mercado) ficam abaixo de linguagens emergentes na plataforma.
O que a amostra de 1.000 mostra e a de 100 não: a força de TypeScript (174) e Rust (57), e a
consolidação do recorte "N/A" (87, 8,7%) como grupo próprio para a RQ07. Na amostra de 100 os "sem
linguagem" eram 13 e o padrão não se distinguia de ruído.

### RQ06: Issues fechadas

**Hipótese:** altíssima taxa de issues fechadas (mediana > 80%), reflexo de manutenção ativa.

**Resultado:** excluídos os 43 repositórios com `total_issues == 0` (a coleta grava `0.0` nesses
casos, taxa falsa), restaram **957**; mediana de **87,5%** (Q1 70,49%, Q3 96,77%), com 430
repositórios (44,9%) acima de 90%.

**Veredito: confirmada.** A mediana supera os 80% da hipótese mesmo sem os 43 casos artificiais. A
divergência com a amostra de 100 (mediana de 92,8%) é a mesma cauda das RQs anteriores: os 1.000
trazem projetos de conteúdo e bibliotecas médias com mais issues abertas acumuladas, o que derruba
a mediana em ~5 p.p. sem mudar o veredito.

**Nota de consistência:** a validação da S02 (issue #16 e README) citou **89,28%**; o recálculo
sobre o snapshot consolidado `all_rqs.csv` reproduz **87,5%**; o valor de 89,28% não é reproduzível
a partir do snapshot atual em nenhum recorte testado. Este relatório usa sempre o valor verificável
do snapshot; a divergência do README fica registrada para conferência na S03.

### Fechamento: o que os 1.000 mostram e os 100 não

As seis RQs se confirmam nas duas amostras, mas a escala de 1.000 muda o *tipo* de resposta: os 100
davam a impressão de um conjunto homogêneo de projetos muito ativos; os 1.000 revelam que
popularidade não é proxy de saúde uniforme. A cauda traz repositórios de conteúdo (listas, livros,
roadmaps) que não são software. É essa cauda que explica as quedas sistemáticas de mediana (PRs,
releases, issues) e os fenômenos que a amostra pequena escondia: os gigantes que não usam o fluxo de
PR do GitHub (RQ02), a fração estável de projetos sem release nenhum (RQ03), a cauda de arquivados
que só `pushedAt` revela (RQ04) e o grupo "sem linguagem" grande o bastante para virar recorte
próprio (RQ05). As métricas de engenharia só respondem com os recortes declarados: recorte por
natureza do repositório, por uso da ferramenta e por publicado/não publicado.

## 5. Configuração do Processo

*[PENDENTE - Fechamento no relatório final]*
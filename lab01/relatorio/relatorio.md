# Relatório Lab01

## 1. Introdução

Este documento consolida a primeira etapa do laboratório para analisar os 1.000 repositórios mais populares do GitHub. Abaixo estão as hipóteses informais escritas pelos integrantes para as seis RQs do projeto:

- **RQ01:** Repositórios populares devem ser majoritariamente maduros, mas com uma cauda de projetos recentes que viralizaram rápido como já apontava a análise extra dos 100, onde a faixa com menos de 1 ano tinha a maior mediana de estrelas. A mediana de idade seguir próxima entre 100 e 1000 repositórios (8,3 → 7,7 anos) é consistente com essa hipótese de duas populações.
- **RQ02:** Espera-se volume alto de PRs aceitas na mediana, mas a métrica tem viés conhecido: projetos que não usam PR do GitHub como fluxo principal aparecem com zero, o que não significa baixa contribuição externa de fato.
- **RQ03:** Espera-se que sistemas populares lancem releases com frequência, mas a métrica deve ser bimodal em vez de ter um valor típico único: um grupo grande não usa *GitHub Releases* de jeito nenhum (27,5% nos 1.000), ou porque não é software, ou porque versiona por tag, como `torvalds/linux` e `golang/go`. Entre os que usam, a cadência deve ser alta. A validação é consistente com isso: nenhuma release em um quarto da amostra e ~15 releases por ano na mediana dos 725 que publicam. Por isso a resposta sai de `releases_por_ano` com os dois recortes declarados, e não do total bruto, que favorece repositório antigo.
- **RQ04:** Espera-se que sistemas populares sejam atualizados com muita frequência, com mediana de poucos dias desde o último push, com uma cauda de projetos arquivados que continuam estrelados por reputação acumulada (`atom/atom`, `adobe/brackets`). Mediana de 3 dias e 11,4% parados há mais de um ano sustentam as duas partes. A hipótese só é testável com `pushedAt`: por `updatedAt` a mediana cai para 43 minutos e a cauda de abandonados desaparece do gráfico.
- **RQ05:** Espera-se que os projetos de maior sucesso sejam desenvolvidos predominantemente nas linguagens que dominam o mercado (tendo como referência o Octoverse 2026, o TIOBE Index Oficial e o Artigo Caiena). A justificativa é estrutural: linguagens populares oferecem os maiores ecossistemas de bibliotecas e uma vasta massa de desenvolvedores aptos a contribuir.
- **RQ06:** Espera-se encontrar uma altíssima taxa de issues fechadas (mediana > 80%). A saúde de um grande projeto open-source depende da manutenção ativa; uma alta taxa de resolução comprova que os mantenedores engajam com a comunidade e não deixam bugs se acumularem, o que é vital para manter a popularidade.

## 2. Metodologia

A coleta utiliza a API GraphQL do GitHub. A query usa o filtro `search(type: REPOSITORY)` integrado com paginação em cursores (`after`) para extrair os 1.000 repositórios com maior quantidade de estrelas.

### Limitações conhecidas da coleta

Algumas particularidades dos dados já foram mapeadas nas amostras iniciais e são tratadas na análise:

- **Fonte de "Linguagens Mais Populares" (RQ05):** Fixamos como fontes oficiais o Octoverse 2026, o [TIOBE Index Oficial](https://www.tiobe.com/tiobe-index/) e o [Artigo Caiena](https://www.caiena.net/blog/linguagens-de-programacao-mais-usadas).
- **Taxa de Pull Requests Fechados (RQ02):** A API conta os PRs integrados de qualquer autor na métrica `merged_pull_requests`. Ela não diferencia a contribuição do core team da contribuição de um desenvolvedor externo.
- **Linguagem Principal "N/A" (RQ05):** Alguns projetos não têm a linguagem preenchida. Para que o Pandas não os descarte como dados faltantes, é obrigatório ler o CSV com `keep_default_na=False`.
- **`pushedAt` vs `updatedAt` (RQ04):** Adotamos a data do último envio (`pushedAt`) porque o campo `updatedAt` sofre alteração com qualquer mudança básica (receber estrela, mudar label) e mascara repositórios já abandonados.
- **Ausência de Releases (RQ03):** Listas, tutoriais e livros não são software e não costumam abrir *Releases*, o que puxa o total de repositórios com "zero releases" para cima.
- **Repositórios sem Issues (RQ06):** Repositórios com `total_issues == 0` costumam gerar a taxa enganosa de `0.0`. Eles precisam ser desconsiderados do cálculo para não jogarem a mediana de fechamento para baixo.

## 3. Resultados

*[PENDENTE - Fechamento na S03]*

## 4. Discussão (Hipótese vs Resultado)

*[PENDENTE - Fechamento na S03]*

## 5. Configuração do Processo

*[PENDENTE - Fechamento no relatório final]*

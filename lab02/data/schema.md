# Schema do CSV de coleta — Lab02

Cada **trial** (um par integrante × kata × tratamento) é **uma linha** deste CSV. É a base de dados
única do experimento: o script de cronometragem (RQ1, Issue #40) grava as colunas de tempo/testes e o
script de métricas estáticas (RQ3, Issue #41) grava as colunas de estrutura, **no mesmo arquivo e no
mesmo cabeçalho**. O cabeçalho de referência está em [`trials_template.csv`](trials_template.csv).

O arquivo consolidado da execução (Lab02S02) fica em `lab02/data/trials.csv`.

## Colunas

| Coluna | Tipo | Unidade / valores | RQ | Preenchida por | Descrição |
|---|---|---|---|---|---|
| `integrante` | texto | login do GitHub (`mateusdsoc`, `Athoosz`, `RafaelMouraG`) | — | manual/#40 | Quem executou o trial. |
| `kata` | texto | id do kata (ex.: `k1`) | — | manual/#40 | Qual exercício foi resolvido. |
| `tratamento` | texto | `com_ia` \| `sem_ia` | indep. | manual/#40 | Variável independente: uso ou não do assistente de IA. |
| `ordem` | inteiro | 1..N | — | manual/#40 | Posição deste trial na sequência do integrante (para o contrabalanceamento). |
| `tempo_s` | inteiro | segundos | RQ1 | #40 | Tempo até todos os testes de aceitação passarem ("time-to-green"). Se censurado, vale `2100`. |
| `censurado_35min` | booleano | `true` \| `false` | RQ1 | #40 | `true` quando o trial atingiu o time-box de 35 min sem passar em todos os testes. Trial censurado **não é descartado**. |
| `testes_total` | inteiro | contagem | RQ2 | #40 | Número total de testes de aceitação do kata. |
| `testes_passando` | inteiro | contagem | RQ2 | #40 | Número de testes passando ao final do trial. |
| `taxa_sucesso` | decimal | 0.0–1.0 | RQ2 | #40 | `testes_passando / testes_total`. Métrica primária da RQ2 (normaliza katas com nº de testes diferente). |
| `cc_media` | decimal | complexidade | RQ3 | #41 | Complexidade ciclomática média por função/método (`radon cc`). |
| `loc` | inteiro | linhas | RQ3 | #41 | Linhas de código do código final: o `sloc` do `radon raw`. Controle **obrigatório** junto de `cc_media`/`duplicacao_pct`. |
| `duplicacao_pct` | decimal | 0.0–100.0 | RQ3 | #41 | Percentual de linhas duplicadas (`jscpd`). |
| `mi` | decimal | 0–100 | RQ3 | #41 | Índice de manutenibilidade (`radon mi`). Opcional/aprofundamento. |
| `num_prompts` | inteiro | contagem | RQ1 (exploratória) | #40 | Nº de prompts/interações com o assistente de IA. Só faz sentido em `com_ia`; vazio em `sem_ia`. Não obrigatória. |

## Como as colunas da RQ3 são medidas

Escolhas do script de métricas estáticas (Issue #41, `lab02/src/metricas_estaticas.py`), as mesmas em
todos os trials — sem isso as colunas da RQ3 não seriam comparáveis entre si:

- **Escopo:** só o código escrito no trial. Os testes de aceitação vêm prontos com o kata, então
  `test_*.py`, `*_test.py`, `conftest.py` e diretórios `tests/` ficam fora das quatro colunas.
- **`cc_media`:** média sobre funções, métodos e closures. O bloco agregado da classe é ignorado — sua
  complexidade é a soma dos métodos, que já entram na conta à parte, e contar os dois duplicaria.
- **`loc`:** `sloc` do `radon raw` (linhas de código de fato, sem linhas em branco nem comentários),
  somado sobre os arquivos de solução — e não o campo `loc` do radon, que conta o arquivo inteiro.
- **`mi`:** o MI é calculado por arquivo; a coluna é a média ponderada por `sloc`, para um arquivo
  minúsculo não pesar igual ao arquivo principal.
- **`duplicacao_pct`:** `jscpd` com `--min-lines 5 --min-tokens 30`. O padrão de 50 tokens foi baixado
  porque soluções de kata são curtas demais para um clone real atingir esse tamanho.

Quando uma ferramenta não consegue medir (ex.: código final com erro de sintaxe, ou `jscpd` não
instalado), a coluna correspondente fica **vazia** e o script avisa no terminal — melhor um vazio
explícito do que um `0` que a análise leria como "sem complexidade" ou "sem duplicação".

## Convenções

- **Time-box = 35 min = `2100` segundos.** Trial que não passa em todos os testes dentro do tempo é
  registrado com `tempo_s=2100` e `censurado_35min=true` — nunca descartado (descartar distorce a
  comparação a favor do tratamento com mais falhas).
- **Métrica agregada = mediana** por tratamento (não a média), dado o N pequeno. A análise inferencial
  (Lab02S03) usa **Wilcoxon pareado**, consistente com o desenho within-subject.
- Colunas não aplicáveis a uma linha (ex.: `num_prompts` em `sem_ia`) ficam **vazias**, não `0`.
- Booleanos em minúsculo (`true`/`false`).

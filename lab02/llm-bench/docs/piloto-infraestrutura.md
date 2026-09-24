# Piloto de infraestrutura — resultados parciais

Data: 24/09/2026. Registro das tentativas sintéticas executadas com o ambiente descrito em [infra/pilot/README.md](../infra/pilot/README.md). Nenhuma tentativa é oficial nem entra na análise do benchmark.

O piloto está **incompleto**: Sol ainda não foi executado. Gemini foi descartado por Rafael e substituído por MiMo-V2.6-Flash Free no OpenCode.

## 1. Ambiente comum

| Item | Valor observado |
|---|---|
| Imagem | `llm-bench-pilot:20260924`, ID `sha256:3544375cb9a4…fb19`, a mesma em todas as tentativas |
| Base | `debian:bookworm-slim` fixada por digest no Dockerfile |
| Harnesses na imagem | Claude Code 2.1.281, Codex 0.156.1, OpenCode 1.18.32, conferidos por `--version` dentro da imagem, sem rede |
| Tarefa | Entrada sintética exclusiva convertida para maiúsculas em `/workspace/result.txt`, seguida de verificação Python |
| Skills | Nenhuma |

As versões na imagem coincidem com as registradas no host na [verificação inicial](verificacao-ambiente.md).

## 2. Tentativas executadas

Horários em UTC, extraídos do identificador da tentativa. O tempo da tarefa corresponde ao `docker exec` do harness; o tempo total inclui preparação e limpeza. Esses tempos servem apenas para verificar o funcionamento, não para comparar participantes.

| Tentativa | Participante | Prazo | Saída | Tarefa (s) | Entrega correta | Modelo informado pelo harness | Resultado |
|---|---|---|---|---|---|---|---|
| `20260924T145341Z-opus-44e567` | Opus, `claude-opus-5-5`, high | 180 s | 0 | 9,2 | Sim | `claude-opus-5-5` | **Passou** |
| `20260924T145433Z-muse-4e5d52` | Muse, Contributor Free, xhigh | 180 s | 0 | 15,5 | Sim | Não capturado | **Passou**, sem identificador do modelo |
| `20260924T145512Z-gemini-0b7956` | Gemini, `gemini-3.8-flash`, high | 180 s | 1 | 77,0 | Não, sem arquivo | Não capturado | **Falhou**; participante descartado |
| `20260924T145713Z-muse-9aa482` | Muse, Contributor Free, xhigh | 120 s | 0 | 16,3 | Sim | `muse-spark-1.3-contributor-free`, variante `xhigh` | **Passou**, com sessão exportada |
| `20260924T145817Z-gemini-a5ab31` | Gemini, `gemini-3.8-flash`, high | 120 s | 124 | 120,0 | Não, sem arquivo | Não capturado | **Falhou por timeout**; participante descartado |
| `20260924T151203Z-mimo-00c6a9` | MiMo, `mimo-v2.6-flash-free`, sem variante | 180 s | 0 | 18,8 | Sim | `mimo-v2.6-flash-free`, variante `default` | **Passou**, com sessão exportada e consumo registrado |
| `20260924T152034Z-opus-a77b20` | Opus, `claude-opus-5-5`, high | 180 s | 0 | 9,2 | Sim | `claude-opus-5-5` | **Passou**; repetição para validar o consumo |
| — | Sol, `gpt-6-sol`, high | — | — | — | — | — | **Não executado** |

Em todas as sete tentativas:

- Na preparação, home e workspace estavam vazios; o diretório do usuário no host e o socket Docker estavam ausentes; o agente rodou com UID 1001.
- Somente o arquivo de credencial do próprio participante foi provisionado; Muse e MiMo não receberam credencial.
- O proxy bloqueou um domínio fora da lista, e a conexão direta a um IP externo também foi bloqueada.
- A entrada original permaneceu inalterada.
- A remoção dos dois containers e da rede retornou código 0.

## 3. Mudanças no runner entre as tentativas

O runner mudou durante o piloto. Portanto, as tentativas não foram feitas sob configuração idêntica:

- **Prazo:** 180 s nas três primeiras e nas duas últimas (MiMo e a repetição do Opus); 120 s nas duas tentativas entre elas, via `--timeout 120`.
- **Proxy:** `models.opencode.ai` foi adicionado à lista de Muse e Gemini depois da primeira tentativa de Muse. Os resumos não registram o motivo; a primeira tentativa de Muse passou sem esse domínio. O MiMo usa a mesma lista que o Muse.
- **OpenCode:** a exportação da sessão e o registro de `reported_variants` aparecem só nas tentativas a partir de 14:57Z. Por isso, a primeira tentativa de Muse não tem identificador do modelo informado.
- **Registros novos:** horários UTC e consumo de tokens (`usage`) só existem a partir da tentativa do MiMo.
- **Extrator do Claude Code:** depois da repetição do Opus, passou a somar `thinkingTokens` de `modelUsage` como raciocínio e a omitir os limites `contextWindow` e `maxOutputTokens`. O `summary.json` dessa tentativa foi gravado antes da correção e ficou com raciocínio `null`. Os valores da §6 foram recalculados do `stdout.jsonl` salvo, com o extrator corrigido; o resumo original não foi editado.

## 4. Gemini: falhas e descarte

- **Primeira tentativa:** segundo a nota do coordenador anterior, que leu o stderr, o serviço do Google respondeu HTTP 503 por alta demanda. Neste registro, a causa foi conferida apenas pelo resumo, que mostra saída 1 sem artefato.
- **Segunda tentativa:** encerrada pelo `timeout` em 120 s, sem artefato. A causa não foi determinada, e os logs não foram analisados.

Rafael descartou o Gemini em 24/09/2026 e escolheu `opencode/mimo-v2.6-flash-free` como substituto no mesmo harness. As duas tentativas permanecem neste registro. Não foram analisadas como falha de entrega: o que houve foram problemas operacionais do provedor ou do harness.

## 5. MiMo-V2.6-Flash Free

- **Identificador:** `opencode/mimo-v2.6-flash-free` no catálogo local do OpenCode, lançado em 22/09/2026, com contexto de 200 mil tokens e saída de até 32 mil.
- **Esforço:** o catálogo não expõe variantes, então não há nível de raciocínio selecionável. O runner omite `--variant`, e o harness registrou a variante `default`. A capacidade de raciocínio está declarada no catálogo.
- **Condições da rota:** segundo a [página do OpenCode Zen](https://opencode.ai/docs/zen/#privacy), a oferta está disponível "por tempo limitado", e os dados coletados durante o período gratuito podem ser usados para melhorar o modelo. Enviar só material sintético ou autorizado, como no Muse. A coleta oficial pode ser afetada se a rota gratuita for encerrada.
- **Custo:** o catálogo informa preço zero, e o harness informou custo 0. A estimativa de custo de API da GQM (M9) exige um preço público do mesmo modelo em rota paga. Enquanto esse preço não existir, a estimativa fica ausente, e não zero.
- **Consumo informado na tentativa**, soma de três eventos `step_finish`:

| Entrada | Saída | Raciocínio | Cache lido | Cache escrito | Custo informado |
|---|---|---|---|---|---|
| 1.817 | 181 | 374 | 14.592 | 0 | US$ 0 |

Se a entrada inclui ou não os tokens de cache no OpenCode não está verificado; o runner registra isso como `input_includes_cache: null`.

## 6. Consumo informado na repetição do Opus

| Entrada | Saída | Raciocínio | Cache lido | Cache escrito | Custo informado |
|---|---|---|---|---|---|
| 8 | 437 | 88 | 17.825 | 622 | US$ 0,0173 |

No Claude Code, `input_tokens` não inclui os tokens de cache, que aparecem à parte. O raciocínio vem de `modelUsage.thinkingTokens`. Pela cobrança da API da Anthropic, ele integra a saída, mas o registro de `usage` não soma as duas categorias.

O login é via assinatura claude.ai. Por isso, o custo que o Claude Code informa é uma estimativa do próprio harness, não um valor cobrado. Na GQM, esse número fica separado da estimativa de M9.

## 7. Verificações complementares

| Verificação | Resultado |
|---|---|
| `scripts/check-isolation-baseline.sh` sobre a imagem do piloto | Passou, código 0; repetida em 24/09/2026 para este registro |
| Timeout e cgroup: container com 128 MiB e 64 processos; tarefa de 10 s encerrada em 1 s | Passou: código 124, arquivo parcial preservado, arquivo tardio ausente, limites de memória e processos visíveis no cgroup |
| Extração de `usage` com eventos sintéticos dos três formatos | Passou |
| Extração de `usage` em tentativa real | Validada nos formatos do OpenCode (MiMo) e do Claude Code (repetição do Opus); falta o Codex |

A verificação de timeout e cgroup foi executada pelo coordenador anterior, e seu resultado foi transcrito do terminal. Ela exercita o `timeout` e os limites de cgroup em um container mínimo, sem agente.

## 8. O que o piloto ainda não cobre

- **Sol.** Deve ser o último a rodar. Consome a cota ChatGPT/Codex, que estava esgotada no momento deste registro. Essa tentativa também valida a extração de `usage` no formato do Codex.
- **Skills, entrega com árvore de código, congelamento e avaliação em ambiente limpo.** Não exercitados; ver as limitações em [infra/pilot/README.md](../infra/pilot/README.md).
- **Dependências baixadas em runtime** pelo OpenCode. Ainda não foram congeladas.

## 9. Métricas adicionadas durante o piloto

Rafael pediu que a coleta registre também tempo, consumo de tokens (para estimar custo em chamadas de API), stack escolhida e tempo de resposta das APIs construídas. As definições candidatas estão na [GQM](gqm.md), §3 e §6.

No piloto sintético, somente tempo e tokens são observáveis. Stack e tempo de resposta dependem de uma entrega da tarefa real e serão exercitados com o avaliador.

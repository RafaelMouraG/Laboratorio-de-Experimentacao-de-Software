# Runner da coleta

`scripts/run-attempt.py` executa uma tentativa da tarefa do encurtador: o agente roda inteiro num container novo, a entrega é congelada e o [avaliador](../../docs/avaliador.md) a verifica num ambiente limpo. Nenhuma tentativa é oficial enquanto o protocolo não for congelado; o resumo registra `official_collection: false` e `phase: "piloto"`.

Estado em 24/09/2026: validado só **sem modelo**, com o participante `simulado` e testes de timeout e de registro da configuração (§4). Nenhuma tentativa real com os participantes foi executada.

## 1. Execução

Na raiz do repositório, com Docker, os três CLIs e a imagem `llm-bench-runtime:20260924`:

```sh
python3 scripts/run-attempt.py opus --dry-run    # prompt, rede e comando, sem containers nem credenciais
python3 scripts/run-attempt.py simulado          # ponta a ponta sem modelo: copia a referência
python3 scripts/run-attempt.py opus              # tentativa real; também muse, sol e astra
python3 scripts/run-attempt.py muse --timeout 1800 --no-evaluate
```

Cada comando executa uma única tentativa, sem repetição automática. A ordem e o número de repetições são decisões do protocolo. Os parâmetros estão em [config.json](config.json); os marcados "provisório" ainda não foram decididos (§5).

O código de saída é 0 quando a tentativa foi executada, congelada e avaliada sem erro operacional e sem sobras. Não depende de `A_i`: uma entrega rejeitada é um resultado, não uma falha do runner.

## 2. Fluxo

1. **Prompt.** O preâmbulo de `config.json` seguido da Parte A do [contrato](../../docs/contrato-encurtador.md), sem o título de coordenação. O único placeholder, o prazo de prontidão em A2, recebe o valor que o avaliador usa (`evaluator/config.json`, hoje 60 s). O runner recusa enviar o texto se restar `[A DEFINIR]`, `Parte B` ou `reservad`. Registra os SHA-256 do contrato, da Parte A e do prompt e salva `prompt.md`.
2. **Rede.** Rede Docker `--internal` e o proxy da imagem (`/opt/pilot/proxy.py`), liberando CONNECT na porta 443 para os domínios do provedor do participante e os seis registros de pacotes. Nenhuma porta é publicada no host.
3. **Container do agente.** Mesmas restrições do piloto e da validação da imagem:
   - raiz somente leitura, UID 1001, `--cap-drop ALL`, `no-new-privileges` e `--init`;
   - tmpfs **com `exec`** em `/tmp`, `/home/agent` e `/workspace`;
   - `sleep infinity` como processo principal, porque o `sleep 1200` da imagem encerraria o container no meio de uma tentativa longa.
4. **Provisionamento.**
   - O home e o workspace começam vazios, o que é verificado.
   - Recebem só a credencial do próprio participante, pelo mecanismo do piloto: stdin e permissão 0600 no tmpfs.
   - O harness recebe a configuração, e `~/.m2/settings.xml` recebe o proxy, como A2 promete ("O Maven já vem configurado com o proxy").
   - A rede é conferida: `pypi.org` alcançável, `example.com` bloqueado pelo proxy e saída direta a IP bloqueada. Se a verificação falhar, a tentativa não começa.
5. **Tentativa.** O harness roda em `/workspace` sob `timeout` com SIGTERM e, depois da tolerância, SIGKILL. O sinal vai ao grupo de processos do comando.
6. **Congelamento.**
   - Processos remanescentes, como servidores em segundo plano, são encerrados.
   - O `/workspace` inteiro é empacotado em `delivery.tar`, com permissão 0600. Pelo contrato, o conteúdo do diretório é a entrega; home e `/tmp` são descartados.
   - Registra o SHA-256 do tar, o hash da árvore (o mesmo do avaliador), os manifestos e lockfiles e se a entrega contém algum valor de credencial.
7. **Limpeza.** Containers e rede `llmbench-attempt-<run_id>-*` são removidos num `finally`, e a ausência de sobras é conferida.
8. **Avaliação.** `evaluator/evaluate.py` roda sobre `delivery.tar`, depois da limpeza, em containers novos. O resumo da tentativa traz `A_i`, S/V/U e os requisitos V e U.

## 3. Evidências

Ficam em `.pilot/attempts/<run_id>/`, que o Git ignora e que tem permissão 0700:

- `summary.json`;
- `prompt.md`;
- `stdout.jsonl` e `stderr.txt`, com credenciais conhecidas redigidas;
- `proxy.log`;
- `session.json`, quando o harness é OpenCode;
- `delivery.tar`;
- `eval/`.

O `summary.json` registra:

- **Configuração:**
  - participante, modelo solicitado, esforço, imagem e ID, versão do harness, recursos, prazo e comando (com o prompt substituído por referência);
  - arquivo e hash da configuração do runner;
  - skills (nenhuma) e hosts liberados.
- **Configuração efetiva do Claude Code**, em `harness_init`: ferramentas, skills e agentes embutidos, plugins, modo de permissão e versão. Quando as ferramentas efetivas diferem das pedidas, o resumo traz `tools_mismatch`.
- **Tempos (M8):** horários UTC de início, início e fim da tarefa, congelamento e término, além das durações.
- **Consumo (M14):** extraído com as funções validadas do `run-pilot.py`, na semântica de cada harness. Fica `null` quando não é observável.
- **Modelos e variantes informados pelo harness.** No OpenCode, vêm da sessão exportada. `session_export` traz o código de saída, o stderr, o tamanho e o erro da exportação. O runner grava o export num arquivo do container e o lê com `cat`, porque no OpenCode 1.18.32 o `export` escrito num pipe é truncado em 128 KiB, com código 0.
- **Término do harness (`harness_end`):** `reason` dos `step_finish` no OpenCode; `subtype` do `result` e `stop_reason` no Claude Code; tipos de evento no Codex. `output_limit_hit` indica resposta interrompida pelo limite de saída do modelo: `length` no OpenCode, `max_tokens` no Claude Code. No Codex, fica `null`, porque o formato não foi validado. `stdout_lines` conta as linhas e as que não são JSON.
- **Avisos (`warnings`):** entrega sem arquivos, término por limite de saída, sessão do OpenCode não exportada e última linha do stdout que não é JSON (possível truncamento). Os avisos não alteram `ok` nem o código de saída: descrevem o resultado, não uma falha do runner.
- **Entrega, avaliação, destinos vistos pelo proxy, processos encerrados antes do congelamento e códigos de limpeza.** Em `delivery`, `entries` conta arquivos e diretórios, e `files`, só arquivos.
- **Recursos do container da tentativa (`resources_observed`)**, lidos do cgroup antes de encerrar os processos:
  - pico e valor atual de memória, com a composição (`anon`, `file`, `shmem`);
  - eventos de memória, inclusive `oom_kill`, que gera aviso;
  - CPU total, de usuário e de sistema, e *throttling*;
  - pico de processos e E/S;
  - uso de disco de `/workspace`, do home e de `/tmp`.
  
  É o container inteiro: harness, ferramentas e processos do agente. O pico de memória inclui tmpfs e cache de arquivos.
- **Atividade do agente (`activity`):** chamadas de ferramenta por tipo, segundo os eventos do harness. No Claude Code, também turnos, duração da API e negações de permissão; no OpenCode, passos e ferramentas com erro; no Codex, mensagens e comandos com saída ≠ 0. Comandos que o próprio Codex recusa não aparecem nos eventos, só no `stderr.txt`.
- **Rastreabilidade:** `runner_sha256` (hash deste script), `image_rootfs_sha256` e `image_created`. Com o armazenamento containerd do Docker, o ID da imagem é o digest do índice OCI, que muda a cada build por causa da atestação de proveniência. O conteúdo é identificado pelas camadas.

Não publicar esses arquivos sem revisão: o stdout do agente e a entrega podem conter trechos inesperados.

## 4. Validação em 24/09/2026

Nenhuma destas execuções chamou modelo ou leu credencial.

| Verificação | Resultado |
|---|---|
| `--dry-run opus` | Prompt com A1–A7, prazo de 60 s preenchido e nada da Parte B; hosts do provedor mais os seis registros |
| `simulado`, ponta a ponta | Preflight e rede OK (`ALLOW pypi.org`, `DENY example.com`); entrega congelada com o mesmo hash de árvore do diretório de referência; avaliação `A_i = 1`, 35 S; limpeza sem sobras; cerca de 9 s |
| Estouro de prazo (harness `shell` de teste, prazo de 60 s) | Código 124; arquivo parcial congelado e arquivo "tarde" ausente; servidor em segundo plano encerrado; limpeza sem sobras |
| Flags do Claude Code 2.1.281, offline | Aceitas. `TodoWrite` e nomes inexistentes são ignorados sem erro, o que motivou o registro de `harness_init` e `tools_mismatch`, testado com um evento `init` sintético |
| Configuração do OpenCode 1.18.32, offline | `opencode debug config` resolve as permissões configuradas |

O harness `shell` só é aceito por um `--config` alternativo; ele não existe na configuração padrão.

Depois do piloto com a tarefa real ([registro](../../docs/piloto-tarefa-real.md)), o runner passou a exportar a sessão do OpenCode por arquivo e a registrar `harness_end` e `warnings`. Verificações sem modelo, em 24/09/2026:

- `harness_end` sobre o `stdout.jsonl` salvo das duas tentativas: MiMo com `last_reason: length` e `output_limit_hit: true`; Muse com `stop`. Também sobre eventos sintéticos do Claude Code e do Codex.
- Export de sessões importadas de 9 KB a 820 KB num container da imagem: o método antigo truncou em 131.072 e 163.840 bytes, com JSON inválido e código 0; o novo exportou as quatro completas.
- `simulado` de ponta a ponta: 35 S, sem avisos, sem sobras.
- Harness `shell` sem saída, com configuração alternativa: aviso de entrega sem arquivos e `ok: true`.

Na tentativa real seguinte (`20260924T180503Z-mimo-393380`), a sessão do OpenCode foi exportada com 142.965 bytes, acima do limite que truncava o método antigo, e o resumo registrou `harness_end.last_reason: length` e os avisos de entrega vazia e de limite de saída. Na tentativa real do Opus (`20260924T184717Z-opus-474850`), `harness_end` registrou `stop_reason: end_turn` a partir do evento `result`. No stream real, as mensagens do assistente trazem `stop_reason` nulo, então a detecção de limite depende do `result`.

## 5. Decisões provisórias e pendentes

Estão em `config.json` e não foram decididas por Rafael:

- **Prazo por tentativa:** **1800 s, decidido por Rafael em 24/09/2026** a partir do piloto com a tarefa real, com 10 s de tolerância.
- **Recursos do container:**
  - 4 GiB de memória, 2 CPUs e 512 processos;
  - tmpfs com home de 2 GiB e `/tmp` e workspace de 1 GiB.
  A memória de tmpfs conta no limite.
- **Texto do preâmbulo do prompt:** idêntico para todos os participantes. Diz que não há interação humana, que `/workspace` é o diretório de trabalho e que seu conteúdo é a entrega.
- **Ferramentas e permissões por harness:**
  - Claude Code: Bash, Read, Write, Edit, Glob e Grep.
  - OpenCode: bash, read, edit, glob, grep, list e as ferramentas de tarefas.
  - Codex: `danger-full-access` dentro do container.
  Sem web, subagentes, skills ou MCP. A paridade entre harnesses é aproximada: por exemplo, o OpenCode tem ferramenta de lista de tarefas, e o Claude Code, nesta configuração, não.
- **Paridade observada no piloto (documentada, não corrigida, por decisão de Rafael em 24/09/2026)** ([registro](../../docs/piloto-tarefa-real.md)):
  - **OpenCode:** com `"*": "deny"`, a regra padrão `external_directory` fica em `ask`, que vira recusa no `opencode run`. O agente não usa `/tmp` nem o home em comandos que citem esses caminhos. O Muse passou a gravar dados de teste em `/workspace` e os apagou antes do fim.
  - **OpenCode:** a ferramenta bash espera processos em background que herdam a saída, até o timeout de 120 s.
  - **Codex:** a política do próprio harness recusa comandos no estilo `rm -rf`, mesmo com `danger-full-access` e `-a never`. O Sol refez a limpeza em Python.
  - **Claude Code:** o evento `init` lista skills, agentes e o plugin `agents-md` embutidos. Sem as ferramentas de skill e de subagente, eles não podem ser invocados, e nenhum foi usado.
  - **Claude Code e Codex:** usam `/tmp` livremente.
  - **Modelo servido:** o OpenCode informa o modelo pela sessão exportada, e o Claude Code pelo evento `init`. O Codex não informa nos eventos `--json`.
  - **Limite de saída:** detectável no OpenCode (`length`) e no Claude Code (`max_tokens`); no Codex, não.
- **Skills:** nenhuma, como no piloto. A seleção continua em aberto na proposta.
- **Prazo de prontidão no enunciado:** usa o valor provisório do avaliador. Se o valor mudar, o prompt muda junto, e o hash registra a mudança.

## 6. Limitações

- **Credenciais:** lidas dos caminhos do computador de Rafael pelo mesmo código do piloto (`scripts/run-pilot.py`). Em outro computador, é preciso ajustá-los. O runner escolhe a credencial e o extrator de consumo pelo harness (`PILOT_NAME_BY_HARNESS`): Sol e Astra usam a mesma credencial do Codex.
- **Codex:** o formato de consumo continua sem validação em tentativa real, como no piloto.
- **Entrega grande:** um `/workspace` com `node_modules` ou `.venv` é congelado inteiro, como manda o contrato. O tar pode ficar grande, e o `build.sh` do avaliador reinstala as dependências.
- **Isolamento:** o desenho é o mesmo do piloto. DNS, serviços do host e tentativas adversariais não foram certificados.
- **Rotas gratuitas:** as condições de dados e disponibilidade de Muse e MiMo continuam valendo ([piloto](../pilot/README.md)).
- **MiMo retirado:** Rafael retirou o MiMo em 24/09/2026 ([registro](../../docs/piloto-tarefa-real.md)). Não terá substituto. A coleta tem Opus, Sol, Astra e Muse; o Astra foi incluído por Rafael depois do piloto. A entrada `mimo` foi removida de `config.json`. As tentativas já feitas registram em `summary.json` o modelo, o hash da configuração da época (`15781e13…`) e o comando.

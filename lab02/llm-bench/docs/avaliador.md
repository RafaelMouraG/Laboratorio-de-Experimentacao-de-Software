# Avaliador automatizado do encurtador

Versão 0.2 — 24/09/2026. Documento de coordenação, privado: descreve os casos reservados da [Parte B do contrato](contrato-encurtador.md) e **não deve ser entregue aos participantes**. O avaliador verifica os 35 requisitos de classe A do contrato v0.1 sobre uma entrega congelada. Não está congelado: os parâmetros continuam provisórios. As decisões de Rafael de 24/09/2026 estão na §9 e na Parte C do contrato; as Partes A e B do contrato não foram alteradas.

Alterações da versão 0.2: interpretações da §8 confirmadas por Rafael; build sem prazo, com teto operacional de 3600 s; diagnóstico de manifestos e lockfiles; RF11 e RNF02 mantidos separados.

O código está em `evaluator/`:

| Arquivo | Papel |
|---|---|
| `evaluate.py` | Orquestra containers, build, inícios, SIGTERM e restauração; consolida S/V/U, `A_i` e o resumo |
| `checks.py` | Checks HTTP, executados no container cliente |
| `container_helper.py` | Auxiliar dentro do container da entrega: supervisão de `start.sh`, SIGTERM, snapshot, restauração e sonda de rede. Não contém checks |
| `config.json` | Único arquivo de parâmetros, com os valores provisórios |
| `reference/` | Implementação de referência em Python com biblioteca padrão e SQLite |
| `controls.py` | Controles positivos e negativos gerados a partir da referência |

Tudo roda com Python 3.11+ e somente a biblioteca padrão, porque os checks executam sem acesso à rede.

## 1. Execução

Na raiz do repositório, com Docker e a imagem `llm-bench-runtime:20260924` construída conforme [infra/runtime/README.md](../infra/runtime/README.md):

```sh
python3 evaluator/evaluate.py evaluator/reference            # entrega em diretório
python3 evaluator/evaluate.py entrega.tar.gz --label tentativa-x --out /caminho/saida
python3 evaluator/controls.py --list                          # controles disponíveis
python3 evaluator/controls.py --jobs 3                        # referência e todos os controles
python3 evaluator/controls.py --only redirect-301 sem-health
```

- **Entrega:** diretório ou tar (`.tar`, `.tar.gz`, `.tgz` etc.) cuja raiz é a raiz da entrega. Caminhos absolutos ou com `..` no tar são recusados. O resultado registra o SHA-256 da árvore, e diretório e tar com o mesmo conteúdo dão o mesmo hash.
- **Saída:** por padrão, em `.pilot/eval/<run_id>/`, que o Git ignora. Contém `result.json`, `summary.txt`, `build.log`, `proxy.log` e `start-N.log`. Os controles gravam em `.pilot/eval/controls-<UTC>/`, com um `summary.json` consolidado.
- **Código de saída:** 0 quando `A_i = 1`; 1 quando `A_i = 0`; 2 quando a avaliação fica inconclusiva por falha do avaliador ou por erro de uso.

O `result.json` traz `counts` (S, V, U e N), `A_i`, `M3 = S/N` e, por requisito, veredito, resumo e evidência. A evidência mostra requisição e resposta resumidas, com até oito linhas truncadas. Traz também `diagnostics` (build, destinos no proxy, manifestos e lockfiles da entrega, sondas de isolamento, tempos de SIGTERM, arquivos alterados fora de `DATA_DIR`, fixture) e `cleanup`.

## 2. Fluxo

Cada avaliação usa nomes `llmbench-eval-<run_id>-{net,proxy,app,client}`. Nenhuma porta é publicada no host.

1. **Rede e containers.** É criada uma rede Docker `--internal`. O proxy, o `infra/pilot/proxy.py` já presente na imagem, sai pela rede padrão e aceita somente CONNECT na porta 443 para os seis registros de `config.json`: `pypi.org`, `files.pythonhosted.org`, `registry.npmjs.org`, `proxy.golang.org`, `sum.golang.org` e `repo.maven.apache.org`. O container da entrega (`app`) roda:
   - com raiz somente leitura, UID 1001, `--cap-drop ALL`, `no-new-privileges` e `--init`;
   - com tmpfs com `exec` em `/tmp`, `/home/agent` e `/workspace`;
   - com tmpfs em `/data` (`DATA_DIR`) e em `/evaluator` (estado do avaliador).
2. **Cópia.** A entrega é enviada como tar pela entrada padrão e extraída em `/workspace`. `~/.m2/settings.xml` recebe o proxy, porque o Maven 3.9 ignora `HTTPS_PROXY`.
3. **Build.** `./build.sh` roda em `/workspace` com `HTTPS_PROXY`/`HTTP_PROXY` apontando para o proxy, sem `DATA_DIR` nem `BASE_URL`, sob `timeout` no limite operacional. Depois, o log do proxy é salvo, o proxy é removido e processos que o build tenha deixado são encerrados.
4. **Isolamento.** Do container da entrega, conexões a `1.1.1.1:443`, `pypi.org:443` e ao proxy removido devem falhar.
5. **Snapshot.** `/workspace`, `/home/agent`, `/tmp` e `/dev/shm` são guardados em `/evaluator`, com a listagem de arquivos.
6. **Início 1.** O auxiliar executa `./start.sh` numa sessão própria, com `DATA_DIR=/data` e `BASE_URL=http://encurtador.test:9090`. O container cliente, na mesma rede interna, consulta `GET /health` até 200 ou até o prazo. Em seguida roda a fase 1: checks funcionais, de validação e de concorrência, mais a fixture de durabilidade.
7. **Início 2 (RNF09).** SIGTERM ao grupo de processos de `start.sh`, com SIGKILL depois da tolerância. Em seguida, novo `start.sh` com o mesmo `DATA_DIR` e comparação da fixture.
8. **Início 3 (RNF04).** SIGTERM; as quatro raízes do passo 5 voltam ao estado pós-build, e só `DATA_DIR` é mantido. Novo `start.sh` e nova comparação.
9. **Limpeza.** Os logs são copiados, os três containers e a rede são removidos e a ausência de sobras com o prefixo é conferida. Isso acontece num `finally`, inclusive em falha ou Ctrl-C.

A avaliação da referência leva cerca de 8 s. Uma entrega que não fica pronta consome o prazo de prontidão inteiro.

## 3. Regras de veredito

- **S** exige a evidência do check. **V** exige uma não conformidade observada. **U** é usado quando uma pré-condição falhou ou o avaliador não conseguiu concluir. `N = 35`. `A_i = 1` somente com `S = 35`.
- **Pré-condições de execução:**
  - build com código diferente de 0 dá RNF01 = V e os outros 34 requisitos U;
  - servidor que não fica pronto dá RNF02 = V e os outros 33 U, inclusive RF11;
  - fixture incompleta dá RNF09 = U;
  - RNF09 diferente de S dá RNF04 = U.
- **Servidor que cai no meio da fase 1.** Antes de cada check, o avaliador consulta `GET /health`. Se não houver 200, o check fica U, e não V. O check que derrubou o servidor fica V pela própria resposta ausente. O servidor não é reiniciado para continuar.
- **Passos intermediários.** Uma criação que não responde 201 dentro de um check que não é RF01 é pré-condição, e o check fica U.
- **Independência entre requisitos.** Cada check verifica só a propriedade do seu requisito:
  - O status exato 302 é conferido apenas em RF04. Para contar visitas (RF05, RNF06, RNF09) e para o "antes do prazo" de RF09, vale qualquer 3xx com `Location`.
  - Os checks de erro conferem só o status. O corpo de erro é conferido uma única vez, em RN13, contra o `error.code` esperado pela situação, e não pelo status recebido. Assim, 400 no lugar de 422 viola os requisitos de validação, mas não RN13.
  - As comparações de durabilidade usam o estado observado antes do reinício, e não o valor teórico. Uma falha de contagem, portanto, não contamina RNF09.
- **Falha do avaliador.** Quando o avaliador falha (erro do Docker, `checks.py` sem JSON, exceção interna), o check afetado fica U, a avaliação é marcada `inconclusiva (falha do avaliador)` e o código de saída é 2. Um defeito do avaliador nunca vira V.

## 4. Matriz requisito → check

"Exemplo" repete a coluna do contrato: **sim** indica caso visível no enunciado; **não**, caso reservado. A última coluna lista casos que o avaliador acrescentou às sementes da Parte B. São todos reservados, inclusive quando o requisito é visível, e devem ser dedutíveis do enunciado.

### 4.1 Execução, entrega e durabilidade

| ID | Exemplo | Check e condição de S | Acréscimos do avaliador |
|---|---|---|---|
| RNF01 | sim | `./build.sh` retorna 0. Um código ≠ 0 dá V (126: sem permissão de execução; 127: ausente). O build não tem prazo; estourar o teto operacional dá U | — |
| RNF02 | sim | `GET /health` responde 200 dentro do prazo, contado a partir do `docker exec` que inicia `start.sh`. Consulta a cada 0,2 s; se `start.sh` sai com código ≠ 0, o resultado é antecipado | — |
| RNF03 | sim | Servidor pronto e todos os checks executados na rede interna, sem proxy, com as três sondas de saída bloqueadas. Sonda com rota externa dá U. **Nunca dá V** (§7) | Sondas de saída |
| RNF04 | não | Com RNF09 = S: SIGTERM, restauração de `/workspace`, home, `/tmp` e `/dev/shm` ao estado pós-build, `DATA_DIR` mantido e novo início. A fixture segue igual à observada no início 2. Perda de estado dá V; snapshot ou restauração incompletos, ou servidor que não fica pronto, dão U. A lista de arquivos alterados fora de `DATA_DIR` é só diagnóstico | Teste comportamental no lugar do diff |
| RNF05 | sim | `short_url == BASE_URL + "/" + code` com `BASE_URL=http://encurtador.test:9090`, em criação com e sem alias e na consulta | Consulta |
| RNF06 | não | n `GET /{code}` simultâneos, cada um na própria conexão e liberados juntos por barreira: todos 3xx e `visits == n` | — |
| RNF07 | não | m POSTs simultâneos com o mesmo alias: exatamente 1×201 e (m−1)×409; a consulta devolve o link aceito | Consulta do vencedor |
| RNF08 | não | p POSTs simultâneos sem alias: todos 201, com códigos distintos | — |
| RNF09 | sim | Fixture da fase 1: A (alias, `expires_at` +1 dia, 2 visitas), C (código gerado) e B (alias excluído). Após SIGTERM e novo início com o mesmo `DATA_DIR`, A e C mantêm `url`, `visits`, `created_at` e `expires_at` (instantes), e B segue 404 na consulta e no redirecionamento. Se RN09 = S, o alias de B continua 409. Servidor que não volta a ficar pronto dá **V** | Não reutilização do alias após o reinício |

### 4.2 Funcionalidades

| ID | Exemplo | Check e condição de S | Acréscimos do avaliador |
|---|---|---|---|
| RF01 | sim | POST com `https://example.com/p%C3%A1gina/a%2Fb?q=a%20b&x=1&y=%c3%a7` responde 201 e atende a todos estes pontos: `Content-Type: application/json`; `Location` igual a `/api/links/{code}`, ou URL absoluta com esse caminho (§8); seis campos presentes; `url` idêntica; `created_at` RFC 3339 dentro da janela da requisição ± tolerância; `expires_at` null; `visits` inteiro 0 | Janela de `created_at` |
| RF02 | não | 20 criações sem alias; todos os códigos casam com `[A-Za-z0-9]{6,12}` | — |
| RF03 | sim | Alias `Rf03-xxxxxx` → 201 com `code` igual. O mesmo alias em minúsculas também é aceito, como outro código | Sensibilidade a maiúsculas (A3) |
| RF04 | sim | Para a URL de RF01 e para `http://Example.COM:8443/X?y=Z`: `GET /{code}`, sem seguir o redirecionamento, responde 302 com `Location` idêntico byte a byte | Segunda URL |
| RF05 | sim | 3 redirecionamentos e depois uma consulta: `visits == 3` | — |
| RF06 | não | Três consultas, um redirecionamento e mais três consultas: 200, JSON, `code` e `url` corretos, com `visits` constante dentro de cada série | Segunda série |
| RF07 | sim | DELETE → 204 sem corpo; depois, `GET /{code}`, `GET /api/links/{code}` e novo DELETE → 404 | — |
| RF08 | não | `expires_at` = agora + 2 dias com fuso −03:00; a criação e a consulta devolvem o mesmo instante | Consulta |
| RF09 | sim | `expires_at` a E segundos, arredondado para cima ao segundo inteiro. Antes do prazo, 3xx. Depois de E + margem, dois `GET /{code}` → 410, e `visits` não muda entre as consultas antes e depois deles. Consulta indisponível dá U | 410 sem contar visita (A4) |
| RF10 | não | `GET /api/links/{code}` do link expirado → 200, com o mesmo `code` e o mesmo instante em `expires_at` | — |
| RF11 | sim | `GET /health` → 200 no início da fase 1 | — |

### 4.3 Regras de validação e erro

| ID | Exemplo | Check e condição de S | Acréscimos do avaliador |
|---|---|---|---|
| RN01 | não | `{}`, `{"url": 1}` e `{"url": null}` → 422 | — |
| RN02 | sim | `/a`, `example.com`, `https://`, `ftp://x.org` e `javascript:alert(1)` → 422 | — |
| RN03 | não | 2048 caracteres → 201; 2049 → 422 | — |
| RN04 | não | Espaço inicial, final e interno, tabulação e quebra de linha → 422 | — |
| RN05 | não | `HTTPS://example.com` e `Http://example.com/Caminho` → 201, com `url` inalterada | Segundo caso |
| RN06 | não | Aliases de 2 e 33 caracteres, com `/`, `.`, espaço, não ASCII (`ação`) e o número `123` → 422; aliases de 3 e 32 caracteres → 201 com `code` igual | Tipo errado |
| RN07 | não | `api`, `API`, `Health` e `health` → 422 | `health` |
| RN08 | sim | Segundo POST com o mesmo alias → 409; o link original não é sobrescrito | Preservação do original |
| RN09 | não | Criar, excluir (2xx; falha na exclusão dá U) e recriar o mesmo alias → 409 | — |
| RN10 | não | Passado (−1 h), instante atual truncado ao segundo, `2026-13-01T00:00:00Z`, data **futura** sem fuso, `"amanhã"` e o número `12345` → 422 | A semente `2026-09-24T10:00:00` já é passada; o avaliador usa uma data futura para isolar a falta de fuso. Texto e número |
| RN11 | sim | `{`, `[]`, `"x"`, corpo vazio e `null` → 400 | `null` |
| RN12 | sim | Código aleatório válido, `no.such` e `~nada`, nas três operações → 404 | — |
| RN13 | sim | Todas as respostas ≥ 400 dos checks de erro (RF07, RF09, RN01–RN12 e amostras de RNF07) têm `Content-Type: application/json`, `error` como objeto, `error.code` igual ao da situação e `error.message` string. Na referência, são 55 respostas. Sem nenhuma resposta de erro, fica U | — |
| RN14 | não | Dois POSTs com a mesma URL → dois 201 com códigos diferentes | — |
| RN15 | não | POST com `"extra": {"a": [1, 2]}` e `"nota": "x"` → 201 | — |

Fora da aceitação:

- **RNF10:** somente diagnóstico. O tempo até o término após SIGTERM fica em `diagnostics.sigterm`, sem veredito.
- **RNF11:** continua em `not_evaluated` no `evaluate.py`. A latência é medida à parte, como diagnóstico, por `evaluator/latency.py` (§10), com perfil de carga provisório.
- **RNF12 a RNF14:** não entram.

## 5. Parâmetros provisórios

Todos estão em `evaluator/config.json`, marcados "provisório — calibrar", exceto o teto do build, que é operacional. O contrato continua com `[A DEFINIR]`: Rafael confirmou que ainda não há valores.

| Parâmetro | Valor | Origem | Observação |
|---|---|---|---|
| Prazo de prontidão | 60 s | Contrato (A2, RNF02) | Precisa acomodar a JVM; medir com entregas reais |
| Expiração em RF09 | 4 s | Contrato (RF09) | Mais a margem de espera de 1,5 s |
| n, m e p | 50, 20 e 50 | Contrato (RNF06–RNF08) | Os controles de corrida falham com folga nesses valores |
| Tolerância após SIGTERM | 10 s | Contrato (RNF10) | Depois dela, SIGKILL ao grupo |
| Teto do build | 3600 s | Operacional | Rafael decidiu que o build não tem prazo (C3). O teto só evita travar o avaliador; estourá-lo dá U |
| Timeout por requisição | 10 s | Operacional | — |
| Tolerância de relógio | 10 s | Operacional | Janela de `created_at` |
| k (RF05) e amostras (RF02) | 3 e 20 | Operacional | — |
| Recursos | App: 4 GiB, 2 CPUs, 512 processos; cliente: 1 GiB | Operacional | tmpfs: workspace e home 1 GiB, `/tmp` 512 MiB, `DATA_DIR` 256 MiB, snapshot 2 GiB |
| `BASE_URL` | `http://encurtador.test:9090` | Escolha do avaliador | Difere do padrão, como pede RNF05 |

## 6. Resultados de 24/09/2026

### 6.1 Referência

`python3 evaluator/evaluate.py evaluator/reference` deu `A_i = 1`, com **35 S, 0 V e 0 U**, em cerca de 8 s. Nenhum container ou rede com o prefixo sobrou. SIGTERM encerrou o processo em 0,2 s nos três inícios. Nenhum arquivo foi alterado fora de `DATA_DIR`. A mesma referência, empacotada em `.tar.gz` com prefixo `./`, deu o mesmo hash de árvore e o mesmo resultado.

### 6.2 Controles

Cada controle é gerado por substituição textual em `evaluator/reference/`, e cada substituição precisa casar exatamente uma vez. Um controle passa quando os conjuntos de V e de U são **exatamente** os esperados, `A_i` é o esperado, a avaliação termina completa e nada sobra.

Resultado da execução completa com o avaliador 0.2.0 (`python3 evaluator/controls.py --jobs 3`, saída em `.pilot/eval/controls-v0.2/`): **26 de 26 controles passaram**. A versão 0.1.0 teve o mesmo resultado, em `.pilot/eval/controls-final/`. Nenhum container ou rede `llmbench-eval-` sobrou. Os 22 controles negativos deram `A_i = 0`, com V exatamente nos requisitos-alvo. Os três positivos deram 35 S. `build-arquivo-ilegivel` testa a robustez do próprio avaliador: `A_i = 0`, sem V, e somente RNF04 como U.

| Controle | Alteração | V esperado | U esperado | S/V/U obtido | Resultado |
|---|---|---|---|---|---|
| `referencia` | Implementação de referência sem alterações | — (positivo) | — | 35/0/0 | passou |
| `referencia-registros` | Referência com build.sh que baixa de PyPI, npm, proxy Go e Maven Central e start.sh que usa o venv | — (positivo) | — | 35/0/0 | passou |
| `referencia-start-sem-exec` | Referência com start.sh que mantém o shell como pai do Python (sem exec) | — (positivo) | — | 35/0/0 | passou |
| `build-arquivo-ilegivel` | build.sh deixa um arquivo sem permissão de leitura; snapshot incompleto deixa RNF04 inconclusivo | — | RNF04 | 34/0/1 | passou |
| `redirect-301` | Redireciona com 301 em vez de 302 | RF04 | — | 34/1/0 | passou |
| `visitas-perdidas` | Incremento de visitas por leitura e escrita separadas, sem exclusão mútua | RNF06 | — | 34/1/0 | passou |
| `alias-reutilizavel` | Exclusão apaga a linha, e o alias volta a ficar livre | RN09 | — | 34/1/0 | passou |
| `sem-persistencia` | Banco SQLite em memória | RNF09 | RNF04 | 33/1/1 | passou |
| `reinicio-falha` | Não reinicia com o mesmo DATA_DIR (CREATE TABLE sem IF NOT EXISTS) | RNF09 | RNF04 | 33/1/1 | passou |
| `dados-fora-de-data-dir` | Banco gravado no diretório de trabalho, fora de DATA_DIR | RNF04 | — | 34/1/0 | passou |
| `formato-de-erro` | Erro plano: {"error": código, "message": …} | RN13 | — | 34/1/0 | passou |
| `validacao-400` | 400 em vez de 422 nos erros de validação | RN01, RN02, RN03, RN04, RN06, RN07, RN10 | — | 28/7/0 | passou |
| `base-url-ignorada` | short_url sempre com http://localhost:8080 | RNF05 | — | 34/1/0 | passou |
| `expiracao-ignorada` | Nunca responde 410 | RF09 | — | 34/1/0 | passou |
| `sem-health` | GET /health responde 404 (rota em /healthz) | RNF02 | 33 (todos os demais exceto RNF01) | 1/1/33 | passou |
| `build-falha` | build.sh termina com código 1 | RNF01 | 34 (todos os demais) | 0/1/34 | passou |
| `alias-corrida` | Criação com alias por verificação seguida de gravação, sem exclusão mútua | RNF07 | — | 34/1/0 | passou |
| `codigos-repetidos` | Código gerado a partir de um contador lido sem exclusão mútua; colisão sobrescreve | RNF08 | — | 34/1/0 | passou |
| `codigo-curto` | Códigos gerados com 5 caracteres | RF02 | — | 34/1/0 | passou |
| `campos-desconhecidos-rejeitados` | 422 para qualquer campo fora de url, alias e expires_at | RN15 | — | 34/1/0 | passou |
| `fuso-perdido` | expires_at devolvido com o horário local rotulado como UTC | RF08 | — | 34/1/0 | passou |
| `json-invalido-422` | 422 em vez de 400 para corpo inválido, mantendo error.code invalid_json | RN11 | — | 34/1/0 | passou |
| `queda-com-json-invalido` | Processo encerra ao receber JSON inválido; checks seguintes ficam sem servidor | RN11 | RF09, RF10, RN12, RN13, RN14, RN15, RNF04, RNF06, RNF07, RNF08, RNF09 | 23/1/11 | passou |
| `delete-200` | DELETE responde 200 com corpo | RF07 | — | 34/1/0 | passou |
| `esquema-sensivel` | Esquema comparado com distinção de maiúsculas | RN05 | — | 34/1/0 | passou |
| `limite-url-2000` | Limite de URL em 2000 caracteres | RN03 | — | 34/1/0 | passou |

Observações:

- `queda-com-json-invalido` esperava U em RF09, RF10, RN12–RN15, RNF04 e RNF06–RNF09, isto é, todos os checks posteriores à queda. Demonstra a regra do §4 da GQM: a falha fica em RN11, e o que não pôde ser observado fica U.
- `sem-persistencia` e `reinicio-falha` deixam RNF04 U, porque a pré-condição RNF09 falhou; `dados-fora-de-data-dir` separa RNF04 de RNF09.
- `referencia-registros` passou pelo proxy nos seis destinos (`ALLOW` para os seis registros, nenhum `DENY`), com o build usando venv, npm, `go get` e `mvn`.
- Estabilidade: a referência deu 35 S em cinco execuções independentes (avulsa, tar e três rodadas de controles). A referência e os três controles de corrida foram repetidos com cinco avaliações simultâneas, com o mesmo resultado.

Achado durante a construção: na primeira versão, `esquema-sensivel` removia o `.lower()` do esquema. O avaliador deu 35 S, e o controle falhou. A causa era a variante, não o avaliador: `urlsplit` já devolve o esquema em minúsculas, então a variante continuava conforme o contrato. Ela foi corrigida para comparar o esquema bruto. É o tipo de erro que a exigência de V exato detecta.

## 7. Limitações

- **RNF03 não produz V.** Sem uma execução com rede para comparar, uma entrega que precisa da rede em runtime aparece como RNF02 V, ou como falhas funcionais, e RNF03 fica U. O avaliador não atribui a causa.
- **RNF04 é comportamental.** Detecta estado necessário depois do reinício e guardado fora de `DATA_DIR`. Gravações fora de `DATA_DIR` que não são estado, como logs e caches, aparecem só no diagnóstico. `/evaluator` também é gravável pelo UID 1001 e não é restaurado; uma entrega que gravasse ali escaparia. Esse cenário é adversarial e está fora do escopo.
- **SIGTERM ao grupo.** O sinal vai ao grupo de processos de `start.sh`, e não só ao PID (§8). Processos que escapam do grupo, como daemons com `setsid`, são mortos com SIGKILL e listados em `diagnostics.sigterm[].swept`.
- **Concorrência é probabilística.** S em RNF06–RNF08 não prova ausência de condição de corrida. Os controles só mostram que corridas com janela de 20–50 ms são detectadas.
- **Relógio compartilhado.** Expiração e `created_at` usam margens. Com host muito carregado, RF09 pode ficar U, nunca V, quando o redirecionamento "antes" termina depois da expiração.
- **Queda do servidor.** Os checks seguintes ficam U, e não há reinício automático para observar os requisitos restantes. É conservador, mas perde informação.
- **Evidência truncada.** Requisições e respostas são resumidas: corpo de até 240 caracteres e até oito linhas por requisito. Os logs completos de build e de `start.sh` ficam no diretório de saída.
- **Stacks validadas.**
  - Build: validado com PyPI, npm, proxy Go e Maven Central (`referencia-registros`).
  - Servidor: validado só com a referência em Python. A partida da JVM e servidores Node e Go não foram medidos.
  - Proxy: aceita só HTTPS (CONNECT na porta 443); Gradle não é suportado, como na imagem.
- **Isolamento.** O avaliador usa o mesmo desenho do piloto: rede interna, proxy com lista explícita e sondas de saída. Resolução DNS de serviços do host e tentativas adversariais não foram certificadas.
- **Tamanho.** O snapshot e as listagens crescem com `node_modules` ou caches Maven. A listagem para em 50.000 entradas (`truncated`), e o snapshot usa até 2 GiB de tmpfs.
- **Latência (RNF11).** Fora da avaliação: é medida pelo diagnóstico da §10, com perfil provisório.

## 8. Ambiguidades encontradas no contrato

Rafael confirmou em 24/09/2026 todas as interpretações abaixo, sem levá-las ao enunciado. O contrato não foi alterado por elas.

| # | Trecho | Ambiguidade | Interpretação adotada |
|---|---|---|---|
| 1 | A4, RF01 | `Location: /api/links/{code}`: uma URL absoluta com esse caminho é aceitável? | Aceita relativa exata ou absoluta com o mesmo caminho. A leitura literal recusaria a absoluta |
| 2 | B2, RF11 | "Coberto por RNF02": se o servidor não sobe, RF11 é V ou U? | U, como os demais funcionais. Rafael decidiu manter RF11 e RNF02 separados: N = 35 |
| 3 | B1, RNF03 | Não há como observar a violação sem comparar com uma execução com rede | S ou U, nunca V (§7) |
| 4 | A6 | "Processo de `start.sh` encerrado com SIGTERM": o PID do script ou o grupo? Com `sh` sem `exec`, o sinal só ao PID deixaria o servidor órfão na porta 8080 | Grupo de processos, como Ctrl-C num terminal. `referencia-start-sem-exec` passa |
| 5 | A2 | "Manter o servidor em primeiro plano" não corresponde a nenhum requisito | Não verificado. Um `start.sh` que sai com 0 e deixa um daemon passa em RNF02, e o fato fica em `diagnostics.start_exited_before_ready` |
| 6 | A2, RNF01 | Não há prazo para `build.sh` | Sem prazo, por decisão de Rafael (C3). O teto operacional é de 3600 s; estourá-lo dá U, não V |
| 7 | A2 | `DATA_DIR` e `BASE_URL` existem durante o build? | Não. `DATA_DIR` precisa estar vazio no primeiro início |
| 8 | A4 | `alias: null` ou `expires_at: null`: ausência ou tipo errado (422)? | Não testado; a referência trata como ausente |
| 9 | A4 | URL com caracteres não ASCII (IRI) e sua codificação em `Location` | Não testado |
| 10 | A4, RN09, RNF09 | A proibição de reutilizar o alias também precisa sobreviver ao reinício? | Sim, dentro de RNF09, e só quando RN09 = S |
| 11 | A4 | "410 sem contar visita" não tem requisito próprio | Conferido em RF09 |
| 12 | A3 | `code` sensível a maiúsculas não tem requisito próprio | Conferido em RF03 como caso reservado |
| 13 | A3, A4 | RFC 3339 admite `t`/`z` minúsculos, espaço como separador (nota da RFC) e frações com mais de 6 dígitos; offset sem dois-pontos não é RFC 3339 | Na leitura das respostas, o avaliador aceita essas variantes, com precisão de microssegundo. Nas entradas, só testa casos inequívocos |
| 14 | A4 | Regex do alias com `$`: em Python, `$` aceita `\n` final | Não testado; a referência usa casamento completo |
| 15 | A3 | Conteúdo e `Content-Type` de `GET /health` e corpo do 302 | Não verificados. `Content-Type` com parâmetros, como `charset`, é aceito |
| 16 | A2, A3 | `BASE_URL` com caminho, como `https://x/s` | Não testado; o valor usado não tem caminho |
| 17 | A4 | Campos desconhecidos que coincidem com campos do recurso (`code`, `visits`) | Não testado; RN15 usa nomes neutros |
| 18 | A4 | "Redirecionamento com sucesso" para contar visita | Qualquer 3xx com `Location`; o 302 exato fica em RF04 |
| 19 | B6 | Granularidade desigual: RN02 tem cinco casos, e RN05, um na semente | Mantida. O avaliador acrescentou um segundo caso a RN05 |

## 9. Decisões e pendências

Rafael decidiu em 24/09/2026. As quatro primeiras decisões estão também na Parte C do contrato:

- **Script público de testes de fumaça (C4):** não será entregue. Os checks continuam reservados. A coluna "Exemplo" da matriz indica apenas o que o enunciado mostra.
- **Lockfile (C5):** não vira requisito. O avaliador registra em `diagnostics.dependencies` os manifestos e lockfiles presentes, ignorando `node_modules`, `.venv`, `vendor` e similares. `requirements*.txt` só conta como lock quando todas as linhas têm `--hash`; se todas estiverem fixadas com `==`, sem hash, ficam em `pinned_requirements`. Para Maven, que não tem lock padrão, há uma nota. Nada disso afeta o veredito.
- **Prazo do build (C3):** não há prazo. O "Não tem" da conversa anterior significava "sem limite" para o build. O avaliador mantém um teto operacional de 3600 s só para não travar.
- **Rede no `build.sh` (C3):** confirmada a proposta de A2, que libera somente os seis registros de pacotes. É o que o avaliador já faz.
- **RF11 e RNF02:** continuam separados; N = 35.
- **Interpretações da §8:** todas confirmadas, sem mudança no enunciado.

Continuam em aberto:

- **Valores do contrato ainda `[A DEFINIR]` (C3):** prazo de prontidão, segundos até a expiração, n, m e p, e tolerância após SIGTERM. Estão provisórios em `config.json` e devem ser calibrados em piloto com entregas reais, em especial a partida da JVM.
- **Perfil de carga de RNF11:** não decidido. O diagnóstico da §10 usa um perfil provisório, em `rnf11_perfil_carga`.

## 10. Diagnóstico de latência (RNF11, M16)

Acrescentado em 24/09/2026, a pedido de Rafael. Versão 0.2, com o perfil de carga que Rafael adotou no mesmo dia, junto com a Q9 da [GQM](gqm.md). `evaluator/latency.py` mede o tempo de resposta de uma entrega congelada. **Não é aceitação:** não produz veredito, não altera `A_i` e não muda `evaluate.py`. Os resultados estão no [registro do piloto](piloto-tarefa-real.md), §8.

```sh
python3 evaluator/latency.py evaluator/reference --label referencia
python3 evaluator/latency.py .pilot/attempts/<run_id>/delivery.tar --label <nome>
```

**Fluxo.**

1. **Ambiente e build.** O mesmo ambiente limpo do avaliador, reaproveitando `Run` de `evaluate.py`: container novo, build com rede só para os registros e servidor sem rede. Containers, rede e volume usam o prefixo `llmbench-lat-` e são removidos ao final.
2. **`DATA_DIR` em disco:** um volume Docker no SSD do host (`/var/lib/docker`, ext4 em NVMe). Um container de uso único, sem rede e só com a capability `CHOWN`, entrega o volume ao UID 1001. Com `data_dir: "tmpfs"`, repete o ambiente do avaliador.
3. **CPUs separadas.** O servidor fica em `app_cpuset`, e o cliente em `client_cpuset`.
4. **Pré-condição.** Entrega que não compila ou não fica pronta fica **sem M16**, registrada como ausente e sem valor, como pede a GQM.
5. **Sementes.** Cria `seed_links` links antes de medir.
6. **Medição.** Para `GET /{code}` e depois para `POST /api/links`, duas fases por duração, cada uma com aquecimento descartado:
   - **Aberta (taxa fixa):** a requisição *i* é agendada para t₀ + i/R. A latência é contada do instante agendado, então a fila no servidor entra na medida (sem *coordinated omission*). O resultado também traz o tempo de serviço, contado do envio real, e o atraso de envio do cliente, para separar os dois efeitos.
   - **Fechada (saturação):** concorrência fixa, com teto de requisições medidas, para limitar o crescimento de `DATA_DIR` e da memória em servidores rápidos.
7. **Validação e estatísticas.** Cada resposta é validada contra o contrato: 302 com `Location` igual à `url`, ou 201 com objeto JSON e `code`. Os percentis (p50, p90, p95, p99, p99.9 e máximo) usam só as respostas válidas. Respostas fora do contrato e erros de transporte entram na taxa de erro.
8. **Recursos do servidor.**
   - **CPU:** a do cgroup do container da entrega, medida a cada fase, em ms por requisição válida.
   - **Memória:** o pico de RSS (VmHWM) dos processos do servidor. O pico do cgroup não serve: inclui o build e não pode ser zerado.
   - **Disco:** o tamanho de `DATA_DIR` ao final.
9. **Sanidade.** A soma de `visits` dos links semeados deve ser igual ao número de 302 válidos, aquecimento incluído. Isso confirma que a carga chegou ao servidor e foi contada (RNF06).

**Gerador de carga.** `evaluator/loadgen/main.go`, em Go e só com a biblioteca padrão, compilado dentro da imagem, sem rede, e guardado em `.pilot/latency/bin/`. Um cliente em Python seria mais lento que um servidor em Go e mediria a si mesmo.

- **Conexões:** reusa conexões quando o servidor permite (keep-alive) e não segue redirecionamentos.
- **Agendador:** dorme até 2 ms antes do instante agendado e espera ativamente o resto. Com isso, o atraso de envio fica em cerca de 3 a 8 µs, contra ~0,3 ms só com `time.Sleep`.

**Parâmetros.** Estão em `evaluator/config.json`, seção `rnf11_perfil_carga`. O perfil foi adotado; os valores numéricos ainda podem ser revistos.

| Parâmetro | Valor |
|---|---|
| Sementes | 1.000 links |
| Fase aberta | 500 req/s; 5 s de aquecimento e 30 s de medição; até 256 requisições em voo |
| Fase fechada | concorrência 32; 2 s de aquecimento e 10 s de medição; teto de 300.000 requisições medidas |
| `DATA_DIR` | disco (volume Docker) |
| CPUs | servidor em 2–3 (2 CPUs, 4 GiB); cliente em 8–11 (4 CPUs) |
| Tempo limite | 10 s por requisição |
| Repetições | três medições por entrega, que estimam a variação do instrumento |

**Limitações.**

- **Disco:** a latência de escrita depende do SSD e da carga do host. O mesmo hardware vale para todas as entregas, mas não representa outro ambiente.
- **Fase fechada:** mede a saturação daquele nível, não a latência sob a mesma carga. Em servidores rápidos, o teto encurta a janela; no Opus, 300 mil requisições em cerca de 1,6 a 3 s.
- **Taxa de 500 req/s:** fica abaixo da capacidade de todas as entregas do piloto em tmpfs. Em disco, uma entrega mais lenta pode não sustentá-la; o sinal disso é a fila, que aparece na diferença entre latência e tempo de serviço.
- **Memória:** o pico de RSS cresce com o volume de dados que a carga cria. Nos servidores que guardam o estado em memória, como o do Opus, ele depende do perfil.
- **Rede:** cliente e servidor ficam no mesmo host, numa rede bridge interna. A latência não inclui rede real.
- **Versão 0.1:** os resultados com `DATA_DIR` em tmpfs e contagem fixa de requisições ficam no registro do piloto como histórico. Não são comparáveis aos da versão 0.2.

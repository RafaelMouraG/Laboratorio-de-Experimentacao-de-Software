# Contrato candidato do encurtador de URL

Versão 0.1 — 24/09/2026. Documento de coordenação, privado. É uma proposta para revisão de Rafael e ainda não está congelada.

- **Parte A:** enunciado candidato, o único trecho previsto para os participantes.
- **Parte B:** catálogo de requisitos e verificação. Contém a estratégia dos testes reservados e **não deve ser entregue aos participantes**.
- **Parte C:** decisões pendentes.

O contrato segue a [GQM](gqm.md): requisitos obrigatórios definem a aceitação (M1) e o atendimento `S/N` (M3). Requisitos de robustez (M5) são um subconjunto marcado. A execução em ambiente limpo corresponde a M6. Medições de desempenho (M16) e a revisão qualitativa (M12) não entram na aceitação.

Valores marcados como **proposta** são escolhas de desenho deste contrato, feitas para torná-lo testável, e podem ser trocados por Rafael. Valores que dependem de infraestrutura ou calibração estão como `[A DEFINIR]`.

---

## Parte A — Enunciado candidato

### A1. Tarefa

Implemente uma API HTTP de encurtamento de URLs. A linguagem, o framework e a forma de persistência são livres, dentro do ambiente descrito em A2. Trabalhe somente no diretório de trabalho fornecido; ao final, o conteúdo desse diretório é a entrega.

### A2. Ambiente de execução e entrega

A entrega é executada pelo avaliador em um container novo, criado a partir do mesmo ambiente disponível durante o desenvolvimento, como usuário não root. O avaliador segue esta ordem:

1. Copia a entrega para o diretório de trabalho.
2. Executa `./build.sh` uma vez, a partir da raiz da entrega. Durante o build, a rede alcança somente os registros de pacotes listados abaixo.
3. Executa `./start.sh`, que deve manter o servidor em primeiro plano, escutando em `0.0.0.0:8080`. Durante a execução, **não há acesso à rede externa**.
4. Considera o serviço pronto quando `GET /health` responde 200. O prazo para isso é de `[A DEFINIR]` segundos após o início de `start.sh`.

Regras da entrega:

- A persistência deve usar exclusivamente o diretório indicado pela variável de ambiente `DATA_DIR`, que existe, está vazio no primeiro início e é gravável.
- Não use serviços externos ao processo, como outro container ou banco remoto. Bancos embutidos ou arquivos em `DATA_DIR` são permitidos.
- A variável `BASE_URL`, sem barra final, define a base das URLs curtas. Se estiver ausente, use `http://localhost:8080`.
- Inclua um `README.md` com instruções de build, execução e testes.
- Testes automatizados e o README são avaliados na revisão qualitativa, não na aceitação.

Ferramentas disponíveis:

- Python 3.11, com `pip` e `venv`; SQLite 3.40.
- Node.js 24 LTS, com npm.
- Go 1.27.
- Java 25 (Temurin JDK), com Maven 3.9.
- `gcc` e `make`, para compilação nativa.

Não há acesso de administrador, e a raiz do sistema de arquivos é somente leitura. Instalações devem ficar no diretório de trabalho ou no home. Durante o desenvolvimento e o build, os pacotes podem ser obtidos somente de PyPI, npm, proxy de módulos Go e Maven Central. Qualquer outro destino é bloqueado. O Maven já vem configurado com o proxy.

### A3. Recurso "link"

Todas as respostas com corpo usam `Content-Type: application/json`.

```json
{
  "code": "aZ3kP9q",
  "url": "https://example.com/pagina?x=1",
  "short_url": "http://localhost:8080/aZ3kP9q",
  "created_at": "2026-09-24T15:00:00Z",
  "expires_at": null,
  "visits": 0
}
```

| Campo | Regra |
|---|---|
| `code` | Identificador do link, sensível a maiúsculas e minúsculas |
| `url` | URL de destino, exatamente como foi recebida |
| `short_url` | `BASE_URL + "/" + code` |
| `created_at` | Instante da criação no servidor, em RFC 3339 com fuso |
| `expires_at` | Instante de expiração em RFC 3339 com fuso, ou `null` |
| `visits` | Número de redirecionamentos realizados com sucesso |

Instantes são comparados como instantes. `2026-09-24T12:00:00-03:00` e `2026-09-24T15:00:00Z` são equivalentes.

### A4. Operações

| Operação | Sucesso | Erros |
|---|---|---|
| `GET /health` | 200 | — |
| `POST /api/links` | 201 com o link e cabeçalho `Location: /api/links/{code}` | 400, 409, 422 |
| `GET /{code}` | 302 com `Location` igual à `url` do link | 404, 410 |
| `GET /api/links/{code}` | 200 com o link | 404 |
| `DELETE /api/links/{code}` | 204 sem corpo | 404 |

**Criação (`POST /api/links`).** O corpo é um objeto JSON:

| Campo | Obrigatório | Regra |
|---|---|---|
| `url` | Sim | String com URL absoluta, esquema `http` ou `https` (sem distinção de maiúsculas), com host, até 2048 caracteres e sem espaços ou caracteres de controle |
| `alias` | Não | String que casa com `^[A-Za-z0-9_-]{3,32}$`. Não pode ser `api` nem `health`, com qualquer combinação de maiúsculas e minúsculas |
| `expires_at` | Não | String RFC 3339 com fuso, estritamente posterior ao instante da requisição |

Regras da criação:

- Campos desconhecidos são ignorados.
- Cada criação bem-sucedida gera um link novo, mesmo que a mesma URL já tenha sido encurtada.
- Sem `alias`, o servidor gera um código de 6 a 12 caracteres de `[A-Za-z0-9]`, diferente de todos os códigos já existentes.
- Com `alias`, o código do link é o próprio alias. Se esse código já existir, ou tiver existido e sido excluído, a resposta é 409.

**Redirecionamento (`GET /{code}`).** Para um link ativo, responde 302 e soma 1 a `visits`. Para um link expirado (instante atual igual ou posterior a `expires_at`), responde 410 sem contar visita. Para um código inexistente ou excluído, responde 404.

**Consulta (`GET /api/links/{code}`).** Retorna o link, inclusive quando expirado, sem contar visita. Para um código inexistente ou excluído, responde 404.

**Exclusão (`DELETE /api/links/{code}`).** Remove o link. Depois disso, as três operações sobre o código respondem 404, e o código não pode ser reutilizado.

### A5. Erros

Toda resposta de erro tem o formato:

```json
{ "error": { "code": "validation_error", "message": "texto livre" } }
```

| Situação | Status | `error.code` |
|---|---|---|
| Corpo que não é JSON válido ou não é um objeto | 400 | `invalid_json` |
| Campo ausente, de tipo errado ou fora das regras | 422 | `validation_error` |
| `alias` já usado, ativo ou excluído | 409 | `alias_conflict` |
| Código inexistente ou excluído | 404 | `not_found` |
| Link expirado no redirecionamento | 410 | `expired` |

### A6. Consistência e durabilidade

- Requisições simultâneas não podem perder visitas, gerar códigos repetidos nem criar dois links com o mesmo alias.
- Toda alteração confirmada com resposta de sucesso deve continuar válida depois que o processo de `start.sh` for encerrado com SIGTERM e iniciado de novo com o mesmo `DATA_DIR`. Isso vale para criações, visitas e exclusões.
- O encerramento abrupto (SIGKILL) não faz parte do contrato.

### A7. Fora do escopo

Autenticação, contas de usuário, listagem de links, edição de links, limitação de taxa, interface web, métricas, verificação de que a URL de destino existe e proteção contra destinos maliciosos. A ausência desses itens não é penalizada.

---

## Parte B — Catálogo de requisitos e verificação

Classe **A** significa aceitação: requisito obrigatório em M1 e M3. Classe **D** significa diagnóstico: registrado sem efeito sobre a aceitação. A regra usual de priorização, com no máximo 60% de requisitos essenciais, não se aplica aqui. Neste estudo, "obrigatório" é a definição operacional do contrato, e não uma prioridade de produto.

A coluna GQM indica a métrica principal: M3 para correção, M5 para robustez (subconjunto de M3) e M6 para execução. Na coluna Exemplo, "sim" significa que o enunciado mostra o caso de forma explícita; "não" significa um caso reservado, dedutível do enunciado.

### B1. Execução e entrega

| ID | Requisito | Classe | GQM | Verificação | Exemplo |
|---|---|---|---|---|---|
| RNF01 | A entrega deve concluir `build.sh` com código 0 no ambiente limpo | A | M6 | Execução pelo avaliador com o log salvo | sim |
| RNF02 | O servidor iniciado por `start.sh` deve responder 200 em `GET /health` dentro do prazo de prontidão | A | M6 | Consulta repetida até o prazo `[A DEFINIR]` | sim |
| RNF03 | O servidor deve funcionar sem acesso à rede externa durante a execução | A | M6 | Todo o conjunto de testes roda com a rede de execução isolada | sim |
| RNF04 | A entrega deve gravar dados persistentes somente dentro de `DATA_DIR` | A | M5 | Workspace montado somente leitura durante a execução, ou diff do workspace antes e depois | não |
| RNF05 | `short_url` deve usar `BASE_URL` quando definida | A | M3 | Execução com `BASE_URL` diferente do padrão | sim |

### B2. Funcionalidades

| ID | Requisito | Classe | GQM | Verificação | Exemplo |
|---|---|---|---|---|---|
| RF01 | O sistema deve criar um link a partir de uma URL válida e responder 201 com o recurso e o `Location` | A | M3 | POST válido; conferir status, cabeçalho, campos e tipos | sim |
| RF02 | O sistema deve gerar códigos de 6 a 12 caracteres de `[A-Za-z0-9]` | A | M3 | Várias criações sem alias; conferir o formato dos códigos | não |
| RF03 | O sistema deve criar um link com o alias informado como código | A | M3 | POST com alias válido; `code` igual ao alias | sim |
| RF04 | O sistema deve redirecionar com 302 para a URL original | A | M3 | `GET /{code}` sem seguir o redirecionamento; comparar o `Location` byte a byte, inclusive com query e percent-encoding | sim |
| RF05 | O sistema deve contar uma visita por redirecionamento com sucesso | A | M3 | k redirecionamentos seguidos de consulta; `visits == k` | sim |
| RF06 | O sistema deve retornar os dados do link sem contar visita | A | M3 | Consultas repetidas não alteram `visits` | não |
| RF07 | O sistema deve excluir um link e responder 204 | A | M3 | DELETE seguido das três operações, todas com 404 | sim |
| RF08 | O sistema deve aceitar `expires_at` futuro e devolvê-lo como o mesmo instante | A | M3 | POST com fuso diferente de UTC; comparar os instantes | não |
| RF09 | O sistema deve responder 410 no redirecionamento de um link expirado | A | M5 | Link com expiração `[A DEFINIR]` segundos à frente; redirecionar antes e depois do prazo | sim |
| RF10 | O sistema deve continuar retornando os dados de um link expirado | A | M3 | `GET /api/links/{code}` depois da expiração responde 200 | não |
| RF11 | O sistema deve responder `GET /health` com 200 | A | M6 | Coberto por RNF02 | sim |

### B3. Regras de validação e erro

| ID | Requisito | Classe | GQM | Verificação | Exemplo |
|---|---|---|---|---|---|
| RN01 | O sistema deve rejeitar com 422 uma `url` ausente ou que não seja string | A | M5 | Corpos `{}`, `{"url": 1}`, `{"url": null}` | não |
| RN02 | O sistema deve rejeitar com 422 URLs relativas, sem host ou com esquema diferente de http e https | A | M5 | `/a`, `example.com`, `https://`, `ftp://x.org`, `javascript:alert(1)` | sim |
| RN03 | O sistema deve aceitar URLs de até 2048 caracteres e rejeitar as maiores com 422 | A | M5 | Limites: 2048 aceita, 2049 rejeitada | não |
| RN04 | O sistema deve rejeitar com 422 URLs com espaço ou caractere de controle | A | M5 | Espaço inicial, final e interno; tabulação; quebra de linha | não |
| RN05 | O sistema deve aceitar o esquema sem distinção de maiúsculas | A | M5 | `HTTPS://example.com` resulta em 201, com `url` inalterada | não |
| RN06 | O sistema deve rejeitar com 422 um alias fora do padrão | A | M5 | 2 e 33 caracteres, `/`, `.`, espaço, não ASCII; limites de 3 e 32 aceitos | não |
| RN07 | O sistema deve rejeitar com 422 os aliases reservados | A | M5 | `api`, `API`, `Health` | não |
| RN08 | O sistema deve rejeitar com 409 um alias já existente | A | M5 | Segunda criação com o mesmo alias | sim |
| RN09 | O sistema deve rejeitar com 409 o alias de um link excluído | A | M5 | Criar, excluir e recriar o mesmo alias | não |
| RN10 | O sistema deve rejeitar com 422 um `expires_at` passado, igual ao instante atual, malformado ou sem fuso | A | M5 | Datas passadas, `2026-13-01T00:00:00Z`, `2026-09-24T10:00:00` | não |
| RN11 | O sistema deve responder 400 a um corpo que não seja JSON válido ou não seja objeto | A | M5 | `{`, `[]`, `"x"`, corpo vazio | sim |
| RN12 | O sistema deve responder 404 a códigos inexistentes nas três operações por código | A | M5 | Código aleatório e código com caracteres fora do padrão | sim |
| RN13 | O sistema deve usar o formato de erro com os valores de `error.code` definidos | A | M3 | Conferido em todos os casos de erro acima | sim |
| RN14 | O sistema deve criar um link novo a cada POST, mesmo para uma URL repetida | A | M3 | Dois POSTs com a mesma URL produzem códigos diferentes | não |
| RN15 | O sistema deve ignorar campos desconhecidos no corpo | A | M5 | POST com um campo extra resulta em 201 | não |

### B4. Consistência e durabilidade

| ID | Requisito | Classe | GQM | Verificação | Exemplo |
|---|---|---|---|---|---|
| RNF06 | O sistema não deve perder visitas sob redirecionamentos simultâneos | A | M5 | n requisições simultâneas; `visits == n`. Valor de n: `[A DEFINIR]` | não |
| RNF07 | O sistema deve aceitar um único link entre criações simultâneas com o mesmo alias | A | M5 | m POSTs simultâneos; exatamente um 201 e os demais 409. Valor de m: `[A DEFINIR]` | não |
| RNF08 | O sistema deve gerar códigos distintos sob criações simultâneas sem alias | A | M5 | p POSTs simultâneos; todos com códigos diferentes. Valor de p: `[A DEFINIR]` | não |
| RNF09 | O sistema deve preservar links, visitas e exclusões após SIGTERM e novo início | A | M5 | Criar, visitar e excluir; SIGTERM; reiniciar; conferir o estado | sim |
| RNF10 | O processo deve terminar após SIGTERM dentro do prazo de tolerância | D | M6 | Tempo até o término. Prazo: `[A DEFINIR]` | não |

### B5. Diagnóstico e revisão

| ID | Requisito | Classe | GQM | Verificação |
|---|---|---|---|---|
| RNF11 | Latência de `GET /{code}` e `POST /api/links` sob perfil de carga fixo | D | M16 | Percentis p50, p95 e p99 e taxa de erros. Perfil: `[A DEFINIR]` |
| RNF12 | README com instruções de build, execução e testes | D | M12 | Rubrica qualitativa |
| RNF13 | Testes automatizados da própria entrega | D | M12 | Rubrica qualitativa; execução dos testes registrada à parte |
| RNF14 | Stack utilizada | D | M15 | Extração dos manifestos e arquivos da entrega |

### B6. Resumo e rastreabilidade

| Grupo | Aceitação | Diagnóstico |
|---|---|---|
| Execução e entrega (RNF01–RNF05) | 5 | 0 |
| Funcionalidades (RF01–RF11) | 11 | 0 |
| Validação e erro (RN01–RN15) | 15 | 0 |
| Consistência e durabilidade (RNF06–RNF10) | 4 | 1 |
| Diagnóstico e revisão (RNF11–RNF14) | 0 | 4 |
| **Total** | **35** | **5** |

Dos 35 requisitos de aceitação, 19 estão marcados como M5. RF11 é verificado por RNF02 e poderá ser fundido a ele no congelamento, reduzindo `N` para 34.

A granularidade dos requisitos não é uniforme. Por exemplo, RN02 reúne vários formatos inválidos, enquanto RN05 cobre um único caso. Pela GQM (§4), o peso vem do requisito, não do número de testes. Antes do congelamento, é preciso confirmar se essa granularidade representa bem o que se quer medir.

A matriz requisito–teste será construída junto com o avaliador. Os casos da coluna Verificação são sementes dessa matriz, não a matriz completa.

---

## Parte C — Decisões pendentes

### C1. Ambiente para a stack livre — resolvido

Rafael escolheu a opção 1 em 24/09/2026. A imagem `llm-bench-runtime:20260924` foi construída e validada; o conteúdo, os resultados e o que ela exige do runner estão em [infra/runtime/README.md](../infra/runtime/README.md). O registro original do bloqueio segue abaixo.

A imagem do piloto, `llm-bench-pilot:20260924`, oferece somente Python 3.11 sem `pip`. A raiz do sistema de arquivos é somente leitura, o usuário não é root e a rede passa por uma lista de domínios. Nessas condições, o agente não consegue instalar outra linguagem nem dependências. **A stack livre não é viável na imagem atual.**

Opções:

1. **Imagem com várias linguagens pré-instaladas**, por exemplo Python com pip, Node, Go e Java, com versões congeladas, mais registros de pacotes liberados no proxy. A liberdade de stack fica limitada ao que foi oferecido, e Q8 passa a medir a escolha entre essas opções. A imagem cresce.
2. **Instalação de toolchains em espaço de usuário durante a tentativa**, com os domínios de download liberados. Ganha liberdade, mas consome parte do prazo, amplia a lista de rede e introduz versões não congeladas.
3. **Stack fixa.** Contradiz a decisão de stack livre e elimina Q8.

A escolha também define quais registros de pacotes entram no proxy, tanto na tentativa quanto no `build.sh` do avaliador.

### C2. Entrega por scripts em vez de Dockerfile

O contrato usa `build.sh` e `start.sh` executados em um container limpo da mesma imagem. Um Dockerfile foi descartado nesta proposta porque o agente roda sem socket Docker e, portanto, não conseguiria testar o próprio Dockerfile. Com os scripts, o agente pode ensaiar exatamente o que o avaliador fará.

### C3. Valores e parâmetros a definir

| Item | Onde | Observação |
|---|---|---|
| Prazo por tentativa | Protocolo | Deve permitir a entrega do escopo acima; calibrar em piloto com a tarefa real, sem otimizar para uma configuração |
| Rede no `build.sh` | A2, RNF01 | **Resolvido:** Rafael confirmou em 24/09/2026 a proposta de A2: durante o build, somente os registros de pacotes, a mesma lista da tentativa |
| Prazo do `build.sh` | A2, RNF01 | **Resolvido:** Rafael decidiu em 24/09/2026 que não há prazo. O avaliador usa só um teto operacional para não travar; estourá-lo deixa RNF01 inconclusivo (U), e não violado |
| Prazo de prontidão | A2, RNF02 | Inclui o tempo de inicialização de runtimes como a JVM |
| Tempo para a expiração nos testes | RF09 | Margem suficiente para evitar falha por latência do próprio teste |
| n, m e p de concorrência | RNF06–RNF08 | Altos o bastante para expor condições de corrida, sem virar teste de carga |
| Tolerância após SIGTERM | RNF10 | Padrão do avaliador para término forçado |
| Perfil de carga e limites de CPU e memória | RNF11 | Mesmo hardware para todas as entregas; M16 só para entregas que iniciam |

### C4. Escolhas deste contrato

Rafael confirmou em 24/09/2026 as cinco primeiras escolhas abaixo e, no mesmo dia, decidiu a última: **o script público de testes de fumaça não será entregue**.

- **Tamanho do código gerado, entre 6 e 12 caracteres alfanuméricos**, e limites do alias, entre 3 e 32 caracteres.
- **Proibição de reutilizar o alias de um link excluído (RN09).** Evita que um link antigo passe a levar a outro destino, mas aumenta a complexidade.
- **Redirecionamento com 302, e não 301.** Evita cache no cliente, que tornaria a contagem de visitas imprecisa.
- **Status 422 para validação e 400 para JSON inválido.**
- **Sem autenticação e sem listagem.** Reduzem o escopo, mas deixam de fora cenários comuns de robustez.
- **Sem script público de testes de fumaça para os participantes.** Ele ajudaria a reduzir falhas de formato, mas funcionaria como dica e mudaria o que M6 mede.

### C5. Riscos de interpretação

- **Datas e fusos (RF08, RN10):** são fonte conhecida de divergência. Os testes precisam aceitar qualquer representação RFC 3339 válida do mesmo instante.
- **Comparação byte a byte do `Location` (RF04):** exige que o enunciado deixe claro que a URL não é normalizada. O enunciado já diz isso, mas vale conferir no piloto se os agentes interpretam da mesma forma.
- **Relógio:** o avaliador e a entrega compartilham o relógio do host. Os testes de expiração devem usar margens, não instantes exatos.
- **Dependências no build do avaliador:** o `build.sh` baixa as dependências de novo. Sem arquivo de lock, a versão resolvida pode diferir da que o agente testou. O contrato não exige lockfile. **Resolvido em 24/09/2026:** Rafael decidiu não tornar isso requisito. Fica como limitação, e o avaliador registra em diagnóstico os manifestos e lockfiles presentes na entrega.

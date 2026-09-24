# Piloto sintético dos harnesses

Este ambiente verifica autenticação, execução de ferramentas, produção de um arquivo e evidências de isolamento. Não implementa a tarefa candidata do encurtador e não é uma tentativa oficial do benchmark.

## Execução

Na raiz do repositório, com Python 3.11+, os três CLIs instalados e acesso ao Docker:

```sh
python3 scripts/build-pilot.py
python3 scripts/run-pilot.py opus
python3 scripts/run-pilot.py muse
python3 scripts/run-pilot.py mimo
python3 scripts/run-pilot.py sol
```

A ordem respeita a decisão de deixar Sol por último para preservar a cota disponível. Cada comando executa uma única tentativa. Não há repetição automática pelo coordenador; os retries internos dos harnesses podem ocorrer dentro do limite de tempo.

Configurações selecionadas:

| Participante | Modelo | Esforço |
|---|---|---|
| Opus | `claude-opus-5-5` | `high` |
| Muse | `opencode/muse-spark-1.3-contributor-free` | `xhigh` |
| MiMo | `opencode/mimo-v2.6-flash-free` | sem variante; o catálogo não expõe níveis de esforço |
| Sol | `gpt-6-sol` | `high` |

O runner usa as credenciais existentes no computador de Rafael, em caminhos explícitos no script. Em outro computador, esses caminhos precisarão ser ajustados. Ele não executa login, altera assinaturas ou modifica as credenciais originais.

## Fronteiras do ambiente

- Imagem comum baseada em Debian, com os binários locais copiados e hashes registrados; o contexto de build contém somente Dockerfile, proxy e binários.
- Agente inteiro dentro de um container novo, usuário não root, raiz somente leitura, capabilities removidas e `no-new-privileges`.
- Home e workspace começam vazios em tmpfs. Nenhum diretório do host, repositório, histórico, entrega anterior ou socket Docker é montado no agente.
- Somente a credencial necessária é enviada por stdin a um processo de provisionamento e escrita com permissão 0600 no tmpfs do container. Muse e MiMo não recebem credenciais.
- Nenhuma skill global é copiada neste piloto. A seleção de skills para a coleta oficial permanece em aberto.
- Agente em rede Docker interna; um proxy separado aceita CONNECT na porta 443 apenas para uma lista explícita de domínios. Não registra cabeçalhos, caminhos de requisição ou conteúdo TLS.
- Sem portas publicadas no host. São verificados bloqueio de destino não autorizado pelo proxy e bloqueio de conexão direta a um IP externo.
- Container do agente limitado a 2 GiB, duas CPUs e 256 processos. Prazo padrão da chamada: 180 segundos, com encerramento por `timeout` e tolerância de dez segundos para término forçado.
- Containers e rede temporária são removidos ao final, inclusive quando o piloto falha.

O proxy permite domínios de catálogo e de instalação das dependências do OpenCode, além dos provedores selecionados. Essa lista é uma configuração provisória do piloto. O comportamento do agente frente a serviços do host, DNS e tentativas adversariais não foi certificado por esses dois testes de rede.

## Critério do piloto

O coordenador gera uma entrada sintética exclusiva. O agente deve lê-la, escrever a versão em maiúsculas e executar uma verificação Python. O avaliador externo compara o resultado ao original mantido pelo coordenador e verifica que a entrada não foi alterada.

Os logs permitem verificar chamadas às ferramentas. Sucesso não depende apenas da resposta textual `PILOT_OK`.

## Evidências e limitações

Resultados ficam em `.pilot/runs/<identificador>/`, ignorado pelo Git: comando, modelo solicitado, esforço, imagem, verificações iniciais, horários UTC e durações, consumo de tokens informado pelo harness, saída do CLI, hashes, resultado, log de domínios do proxy e códigos de limpeza. Credenciais conhecidas são redigidas antes de salvar a saída. Não publicar os logs sem revisão.

O campo `usage` do `summary.json` fica `null` quando o harness não informa consumo. Cada fonte mantém sua semântica, registrada em `source` e `input_includes_cache`. A extração foi testada com eventos sintéticos e validada em tentativas reais do MiMo (OpenCode) e do Opus (Claude Code). No formato do Codex, ainda não foi validada. O consolidado das tentativas está em [docs/piloto-infraestrutura.md](../../docs/piloto-infraestrutura.md).

Para OpenCode, o runner exporta também a sessão da própria tentativa, quando disponível, antes de descartar o container. Identificadores registrados pelo harness são evidências de seleção e execução, sem equivaler a uma atestação independente dos pesos servidos pelo provedor.

O arquivo `result.txt` local é conservado somente após comprovar igualdade byte a byte com a transformação esperada. O piloto não exporta árvores arbitrárias de código nem implementa ainda o congelamento completo das entregas do benchmark.

Os tempos incluem inicialização do harness e eventuais downloads de SDKs; não são resultados comparativos de eficiência. Os limites e a ausência de skills também não definem a configuração da coleta oficial. Versões de dependências baixadas em runtime precisarão ser congeladas no ambiente definitivo.

A rota [Muse Contributor Free](https://opencode.ai/docs/zen/#privacy) permite uso dos prompts e respostas para treinamento. Segundo a mesma página, no MiMo-V2.6-Flash Free os dados coletados durante o período gratuito podem ser usados para melhorar o modelo, e a oferta vale "por tempo limitado". O piloto envia somente dados sintéticos. Essas condições, e o risco de a rota gratuita deixar de existir antes do fim da coleta, precisam constar do protocolo de coleta e da documentação da configuração.

Gemini (`google/gemini-3.8-flash`) foi descartado por Rafael em 24/09/2026, depois de duas tentativas sem entrega. Essas tentativas permanecem registradas em [docs/piloto-infraestrutura.md](../../docs/piloto-infraestrutura.md).

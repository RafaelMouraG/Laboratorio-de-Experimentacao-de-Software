# Verificação inicial do ambiente

Data: 24/09/2026. Verificações automatizadas realizadas antes do piloto completo. Nenhuma tentativa oficial foi executada e nenhuma chamada de inferência foi feita nesta verificação.

## 1. Ferramentas e autenticação no host

| Componente | Evidência observada | Alcance |
|---|---|---|
| Docker | Cliente e daemon 29.8.1 responderam à consulta | Acesso operacional ao daemon confirmado |
| Claude Code | Versão 2.1.281; `auth status` informou login via claude.ai | Sessão declarada no host; acesso ao modelo e uso no container pendentes |
| Codex | Versão 0.156.1; `login status` informou login via ChatGPT | Sessão declarada no host; acesso ao modelo e uso no container pendentes |
| OpenCode | Versão 1.18.32; `providers list` listou Google via API e OpenAI via OAuth | Credenciais cadastradas; validade para inferência não testada |

As consultas de OpenCode foram executadas com `--pure`, que desabilita plugins externos, para examinar o catálogo sem carregar essas extensões. Isso não define a configuração final do participante.

O sandbox da sessão inicialmente bloqueou acesso ao socket Docker e escrita do log normal do OpenCode. As consultas funcionaram após a concessão de execução com a permissão adequada. Não foi necessário pedir login interativo a Rafael.

## 2. Identificadores e parâmetros

| Participante pretendido | Identificador encontrado | Evidência e pendência |
|---|---|---|
| Opus 5.5 high / Claude Code | `claude-opus-5-5`, com `--effort high` | Identificador na documentação oficial; opção `high` exposta pelo CLI. Falta validar uma requisição com esta combinação e a conta do participante |
| GPT Sol 6 / Codex | `gpt-6-sol` | Identificador na documentação oficial e no catálogo local em cache. Falta escolher esforço e validar requisição |
| Muse 1.3 xhigh / OpenCode | `opencode/muse-spark-1.3-contributor-free`, com `--variant xhigh` | Modelo e variante presentes no catálogo local. Confirmar se esta é a rota pretendida; não presumir equivalência com a rota paga |
| Gemini 3.8 / OpenCode | `google/gemini-3.8-flash` | Modelo presente no catálogo local e na documentação oficial. Descartado depois, em 24/09/2026; substituído por `opencode/mimo-v2.6-flash-free` (ver [registro do piloto](piloto-infraestrutura.md)) |

Detalhes observados:

- O catálogo em cache do Codex expõe para Sol os níveis `low`, `medium`, `high`, `xhigh`, `max` e `ultra`, com padrão `medium`. A página da API documenta `none`, `low`, `medium`, `high`, `xhigh` e `max`. Não equiparar automaticamente o catálogo do harness ao parâmetro da API; validar a combinação escolhida em execução.
- A configuração global atual do Codex seleciona `gpt-6-astra` com esforço `high`. A tentativa de Sol precisará de seleção explícita própria; a configuração global não foi alterada.
- A configuração global consultada do Claude Code usa o alias `opus`. O benchmark deverá selecionar explicitamente o identificador pretendido e registrar a resolução efetiva quando observável.
- O catálogo do OpenCode expõe `minimal`, `low`, `medium`, `high` e `xhigh` para Muse Contributor Free. O metadado de `xhigh` contém `reasoningEffort: xhigh`.
- Para Gemini 3.8 Flash, o catálogo expõe `low`, `medium` e `high`, mapeados para `thinkingConfig.thinkingLevel`.
- O OpenCode Zen documenta também a rota `opencode/muse-spark-1.3`, distinta da variante Contributor Free. A escolha de rota, suas condições e sua disponibilidade precisam ser registradas antes de executar o participante.

Presença em catálogo, credencial cadastrada e documentação pública não comprovam que uma requisição será aceita para uma conta específica.

Fontes oficiais consultadas:

- [Claude Opus 5.5: identificador](https://platform.claude.com/docs/en/models/opus-5-5/overview).
- [GPT-6 Sol: identificador e parâmetros da API](https://developers.openai.com/api/docs/models/gpt-6-sol).
- [OpenCode Zen: rotas Muse e formato dos identificadores](https://opencode.ai/docs/zen/).
- [Gemini 3.8 Flash: identificador e níveis de thinking](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash).

## 3. Checagem básica de isolamento

Foi executado o script [check-isolation-baseline.sh](../scripts/check-isolation-baseline.sh) com uma imagem pública já disponível localmente: `caddy:2.11.4-alpine`, ID local `5f5c8640aae0`. O entrypoint foi substituído por `/bin/sh`; o serviço Caddy não foi iniciado. Essa imagem foi usada apenas como ambiente mínimo com shell, e não como imagem definitiva dos agentes.

Comando executado:

```sh
bash scripts/check-isolation-baseline.sh 5f5c8640aae0
```

O script cria dois containers sequencialmente com remoção automática, sem bind mounts do host, sem rede externa, usuário 65534, raiz somente leitura, capabilities removidas e `no-new-privileges`. Usa armazenamento temporário em memória para `/tmp`. Foram solicitados limites de 128 MiB de memória, uma CPU e 64 processos; o comportamento sob esgotamento desses limites ainda não foi exercitado.

| Verificação | Resultado |
|---|---|
| UID não root | Passou |
| Diretório `/home/rafael-moura` ausente | Passou |
| Socket `/var/run/docker.sock` ausente | Passou |
| Apenas interface loopback no container | Passou |
| Capabilities efetivas zeradas | Passou |
| `NoNewPrivs` ativo | Passou |
| Raiz montada somente para leitura | Passou |
| Criação de marcador em `/tmp` no primeiro container | Passou |
| Marcador ausente no segundo container | Passou |

Código de saída do script: `0`. Os dois containers foram encerrados com `--rm`.

**Limite da evidência:** esta é uma checagem básica da configuração usada. Não certifica resistência a escapes de container nem comprova o isolamento da futura imagem com agente, credenciais, skills e rede para provedores. A mesma verificação deverá ser ampliada e repetida sobre a configuração final. A ausência dos caminhos verificados não é uma busca exaustiva por todo possível acesso ao host.

## 4. O que ainda exige validação

- Preparar imagens dos harnesses e registrar versões dos binários e dependências.
- Disponibilizar apenas a autenticação necessária, sem copiar histórico, memórias ou configurações globais completas.
- Validar chamadas reais a cada modelo dentro dos containers e registrar o modelo efetivo quando observável.
- Verificar a política de rede, os arquivos e instruções carregados e as skills explicitamente selecionadas.
- Exercitar timeout, limites, exportação da entrega e coleta de evidências.
- Repetir tentativas com arquivos sentinela para detectar persistência ou acesso indevido entre ambientes completos.

Essas etapas podem ser automatizadas. A participação manual de Rafael poderá ser necessária se o provedor exigir login interativo, consentimento ou renovação de credenciais. Até esta verificação, nenhuma dessas etapas manuais foi exigida.

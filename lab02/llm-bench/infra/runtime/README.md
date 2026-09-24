# Imagem multi-linguagem candidata

Imagem única para as tentativas e para o avaliador, escolhida por Rafael em 24/09/2026 para viabilizar a stack livre do [contrato](../../docs/contrato-encurtador.md). Ainda não está congelada para a coleta oficial.

## Build e validação

Na raiz do repositório:

```sh
python3 scripts/save-harness-binaries.py            # binários fixos em .pilot/harness-bin, conferidos pelo manifesto
python3 scripts/build-pilot.py --dockerfile infra/runtime/Dockerfile --image llm-bench-runtime:20260924 \
    --harness-dir .pilot/harness-bin
python3 scripts/check-runtime-image.py
bash scripts/check-isolation-baseline.sh llm-bench-runtime:20260924
```

O build registra em `.pilot/images/llm-bench-runtime_20260924.json`, arquivo ignorado pelo Git, o ID da imagem, o hash do Dockerfile e os hashes dos binários dos harnesses.

**Binários fixos (decisão de Rafael de 24/09/2026).** O build da imagem da coleta não copia mais os harnesses do host, que se atualizam sozinhos.

- **Manifesto:** `infra/runtime/harnesses.json`, versionado, fixa versão, SHA-256 e tamanho de `claude` 2.1.281, `codex` 0.156.1, `codex-code-mode-host` e `opencode` 1.18.32.
- **Binários:** ficam em `.pilot/harness-bin/`. `scripts/save-harness-binaries.py` os extrai da imagem validada e confere os hashes. Como as imagens Docker são globais no host, o script recria o diretório em qualquer checkout.
- **Build:** `build-pilot.py` recusa construir a imagem da coleta sem `--harness-dir` e recusa binário com hash diferente do manifesto.
- **Exportação:** `save-harness-binaries.py --save-image` exporta a imagem com `docker save`, em gzip, para `.pilot/images/`, com o SHA-256 ao lado. Isso preserva a imagem inteira, inclusive os pacotes Debian, que um novo build poderia trocar. Exportada em 24/09/2026: `llm-bench-runtime_20260924-f5e1796e3908.tar.gz`, com 0,77 GB.

**ID da imagem.** Com o armazenamento containerd do Docker 29, o ID é o digest do índice OCI, que inclui uma atestação de proveniência gerada a cada build. Um build com todas as camadas em cache produziu o ID `sha256:f5e1796e3908…`, contra `838a7837a0ec…` antes, com a mesma data de configuração (19:35:40Z) e os mesmos binários. O conteúdo é identificado pelas camadas: o runner registra `image_rootfs_sha256`. A imagem `838a…`, usada na repetição do Sol e no Astra, foi descartada pelo Docker ao perder a tag. Pelo cache, o conteúdo dela é o mesmo da `f5e1…`, mas isso não pode mais ser conferido diretamente.

## Conteúdo

| Componente | Versão | Origem |
|---|---|---|
| Base | Debian 12 (bookworm-slim) | Fixada por digest |
| Python | 3.11.2, com `pip` 23.0.1 e `venv`; SQLite 3.40.1 | Pacotes Debian |
| Node.js | 24.21.0 LTS, npm 11.19.0; inclui `node:sqlite` | nodejs.org, SHA-256 verificado |
| Go | 1.27.1, com `GOTOOLCHAIN=local` | go.dev, SHA-256 verificado |
| Java | Temurin JDK 25.0.4.1 LTS | Adoptium, SHA-256 verificado |
| Maven | 3.9.16 | Maven Central, SHA-512 verificado |
| Compilação nativa | `build-essential` (gcc) e `python3-dev` | Pacotes Debian |
| Harnesses | Claude Code 2.1.281, Codex 0.156.1 com o auxiliar `codex-code-mode-host`, OpenCode 1.18.32, copiados do host | Hashes no manifesto do build |

As toolchains oficiais têm versão e checksum fixos no Dockerfile. Os pacotes Debian vêm do espelho no momento do build. O que fica congelado, portanto, é a imagem construída, identificada pelo ID. Reconstruir mais tarde pode produzir pacotes Debian diferentes.

Gradle não está incluído. Um projeto com Gradle Wrapper exigiria liberar `services.gradle.org` e os repositórios de plugins.

## Reconstrução em 24/09/2026: auxiliar do Codex

A primeira imagem, `sha256:aa1c6322f54a…839eb`, não tinha o `codex-code-mode-host`. O Codex 0.156.1 executa as ferramentas por esse auxiliar, que fica na mesma pasta de release do `codex`. Sem ele, nenhuma chamada de ferramenta rodou na primeira tentativa do Sol ([registro](../../docs/piloto-tarefa-real.md), §4.7). Correção, com autorização de Rafael:

- `scripts/build-pilot.py` copia também o auxiliar e registra o hash dele. O build falha se o auxiliar faltar.
- O `Dockerfile` instala o auxiliar em `/usr/local/bin`.
- `scripts/check-runtime-image.py` passa a verificar as versões dos três harnesses e a presença do auxiliar.

Imagem atual: **`sha256:838a7837a0ecddd0d8e1d02f25b5e2e181828061301123102b3f6e047c3d01c6`**, com a mesma tag `llm-bench-runtime:20260924`.

- **Diferença para a anterior:** só a camada dos harnesses. As camadas do Debian e das toolchains vieram do cache do build. `claude`, `codex` e `opencode` têm os mesmos SHA-256 da imagem anterior, e a única adição é o `codex-code-mode-host` (`45ba654b…f1`).
- **Imagem anterior:** preservada como `llm-bench-runtime:20260924-v1-sem-code-mode-host`, para rastrear as tentativas de MiMo, Muse e Opus e a primeira do Sol.
- **Validação:** `check-runtime-image.py`, isolamento, avaliação da referência (35 S) e runner `simulado` (35 S) passaram na imagem nova.
- **Achado:** o Claude Code do host se atualizou sozinho para 2.1.282 entre os builds. Como o build copia o binário do host, a imagem mudaria de versão sem aviso. A reconstrução usou o `claude` 2.1.281 extraído da imagem anterior, posto à frente no `PATH` só durante o build. Antes da coleta, é preciso fixar os binários dos harnesses, por exemplo guardando-os com hash, em vez de copiá-los do host no momento do build.

O auxiliar não é exercitado pela validação: não há como testar a ferramenta de execução do Codex sem chamar o modelo. A repetição da tentativa do Sol (`20260924T193701Z-sol-94fff0`) confirmou que a ferramenta funciona: os comandos executaram, e a entrega foi aceita com 35 S.

## Resultado da validação em 24/09/2026 (primeira imagem)

Imagem `sha256:aa1c6322f54a7b9d01d2663992f2563251bccb26226e7eeba2f43ddc969839eb`, com 2,84 GB.

**Fase 1, sem rede.** Nas mesmas restrições do agente (raiz somente leitura, UID 1001, capabilities removidas, tmpfs), todas as verificações passaram:

- versões das quatro linguagens;
- criação de venv;
- SQLite em Python e em Node;
- `go run`;
- um servidor HTTP com biblioteca padrão respondendo 200 em cada linguagem.

**Fase 2, com proxy.** A lista de destinos liberados continha somente `pypi.org`, `files.pythonhosted.org`, `registry.npmjs.org`, `proxy.golang.org`, `sum.golang.org` e `repo.maven.apache.org`.

- Passaram: `pip install`, `npm install`, `go get` e `mvn dependency:get`.
- Um acesso a `github.com` foi bloqueado.
- O proxy registrou somente os seis registros e a tentativa bloqueada.

O check básico de isolamento também passou sobre esta imagem.

## Requisitos que esta imagem impõe ao runner da coleta

Os pontos abaixo foram observados na validação. O runner do piloto sintético não os implementa. O [runner da coleta](../attempt/README.md) implementa os três primeiros e usa tmpfs de 2 GiB no home:

- **Montagens executáveis.** `/tmp`, `/home/agent` e `/workspace` precisam ser montados com `exec`. Com o padrão `noexec` do Docker, `go run` falhou com `permission denied`, e binários compilados no workspace e módulos nativos do npm também não executariam.
- **Proxy do Maven.** O Maven 3.9 ignora `HTTPS_PROXY` e `-Dhttps.proxyHost`. É preciso provisionar `~/.m2/settings.xml` com o proxy, como fez a validação.
- **Lista de rede.** Os registros de pacotes entram junto com os domínios do provedor de cada participante.
- **Tamanho dos tmpfs.** Caches do Go, npm e Maven e builds Java ocupam o home. A validação usou 1 GiB para o home, contra 512 MiB no piloto. Como a memória de tmpfs conta no limite do container, os limites finais precisam considerar os dois.

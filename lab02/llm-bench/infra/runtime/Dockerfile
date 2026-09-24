# Imagem multi-linguagem candidata para a coleta: agente e avaliador usam a mesma imagem.
# Toolchains oficiais com versão e checksum fixos; pacotes Debian vêm do espelho no momento
# do build e são congelados pela própria imagem (registrar o ID e o manifesto gerado).
FROM debian:bookworm-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251

ARG NODE_VERSION=24.21.0
ARG NODE_SHA256=fd8e59d5a511510f6a298afb548f18c7d2b1be404d8b4a27d94fbe49f56cb2d6
ARG GO_VERSION=1.27.1
ARG GO_SHA256=63d339f0da5ab53635a56f2490a7984dfe12dfcff22ad749f63edaf590168445
ARG JDK_URL=https://github.com/adoptium/temurin25-binaries/releases/download/jdk-25.0.4.1%2B1/OpenJDK25U-jdk_x64_linux_hotspot_25.0.4.1_1.tar.gz
ARG JDK_SHA256=dbb698396d478e7fa2b1e50f4103324b2a99b90569ee27c33f2261f9215cf41e
ARG MAVEN_VERSION=3.9.16
ARG MAVEN_SHA512=831a8591fe20c8243b1dbe7d71e3244f31d1665b0804b2e825e38cbbe5ce0cafb8338851f90780735568773e0a6cd07bbec107cda0b896b008b861075358b6f6

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates git curl ripgrep procps libstdc++6 xz-utils \
    python3 python3-pip python3-venv python3-dev build-essential sqlite3 \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; cd /tmp; \
    curl -fsSLo node.tar.xz "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz"; \
    echo "${NODE_SHA256}  node.tar.xz" | sha256sum -c -; \
    mkdir /opt/node; tar -xJf node.tar.xz -C /opt/node --strip-components=1; rm node.tar.xz; \
    curl -fsSLo go.tar.gz "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz"; \
    echo "${GO_SHA256}  go.tar.gz" | sha256sum -c -; \
    tar -xzf go.tar.gz -C /opt; rm go.tar.gz; \
    curl -fsSLo jdk.tar.gz "${JDK_URL}"; \
    echo "${JDK_SHA256}  jdk.tar.gz" | sha256sum -c -; \
    mkdir /opt/java; tar -xzf jdk.tar.gz -C /opt/java --strip-components=1; rm jdk.tar.gz; \
    curl -fsSLo maven.tar.gz "https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/${MAVEN_VERSION}/apache-maven-${MAVEN_VERSION}-bin.tar.gz"; \
    echo "${MAVEN_SHA512}  maven.tar.gz" | sha512sum -c -; \
    mkdir /opt/maven; tar -xzf maven.tar.gz -C /opt/maven --strip-components=1; rm maven.tar.gz

# Raiz somente leitura na execução: instalações globais do npm vão para o home do agente.
# GOTOOLCHAIN=local impede que o Go baixe outra versão do toolchain durante a tentativa.
ENV JAVA_HOME=/opt/java \
    NPM_CONFIG_PREFIX=/home/agent/.npm-global \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    GOTOOLCHAIN=local \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH=/home/agent/.npm-global/bin:/home/agent/go/bin:/opt/node/bin:/opt/go/bin:/opt/java/bin:/opt/maven/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN useradd --create-home --uid 1001 --shell /bin/bash agent \
    && mkdir /workspace && chown agent:agent /workspace
COPY --chmod=755 claude codex codex-code-mode-host opencode /usr/local/bin/
COPY proxy.py /opt/pilot/proxy.py
USER agent
WORKDIR /workspace
CMD ["sleep", "1200"]

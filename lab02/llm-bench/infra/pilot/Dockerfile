FROM debian:bookworm-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates git python3 curl ripgrep procps libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1001 --shell /bin/bash agent \
    && mkdir /workspace && chown agent:agent /workspace
COPY --chmod=755 claude codex opencode /usr/local/bin/
COPY proxy.py /opt/pilot/proxy.py
USER agent
WORKDIR /workspace
CMD ["sleep", "1200"]

#!/usr/bin/env bash
# Verifica uma configuração mínima; não certifica o isolamento dos agentes.
set -euo pipefail

image_ref=${1:?Uso: bash scripts/check-isolation-baseline.sh IMAGEM_LOCAL_COM_SH}
docker_args=(
  run --rm --pull=never
  --network none
  --read-only
  --user 65534:65534
  --cap-drop ALL
  --security-opt no-new-privileges
  --pids-limit 64
  --memory 128m
  --cpus 1
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m
  --workdir /tmp
  --entrypoint /bin/sh
)

docker "${docker_args[@]}" "$image_ref" -ec '
  test "$(id -u)" = 65534
  test ! -e /home/rafael-moura
  test ! -e /var/run/docker.sock
  test "$(ls /sys/class/net)" = lo
  test ! -e /tmp/llm-bench-attempt-marker
  awk "/^CapEff:/ { if (\$2 != \"0000000000000000\") exit 1; found=1 } END { if (!found) exit 1 }" /proc/self/status
  awk "/^NoNewPrivs:/ { if (\$2 != 1) exit 1; found=1 } END { if (!found) exit 1 }" /proc/self/status
  awk "\$2 == \"/\" { n=split(\$4, a, \",\"); for(i=1;i<=n;i++) if(a[i]==\"ro\") found=1 } END { if (!found) exit 1 }" /proc/mounts
  touch /tmp/llm-bench-attempt-marker
  test -f /tmp/llm-bench-attempt-marker
  echo "PASS: usuário não root, caminhos do host ausentes, socket Docker ausente, somente loopback, capabilities removidas, no-new-privileges e raiz somente leitura."
  echo "PASS: marcador criado no armazenamento temporário da primeira tentativa."
'

docker "${docker_args[@]}" "$image_ref" -ec '
  test ! -e /tmp/llm-bench-attempt-marker
  echo "PASS: segundo container começou sem o marcador da primeira tentativa."
'

echo "Limite: verificação básica, sem agentes, credenciais, skills ou acesso aos provedores."

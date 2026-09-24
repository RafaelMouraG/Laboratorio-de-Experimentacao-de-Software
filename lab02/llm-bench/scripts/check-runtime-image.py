#!/usr/bin/env python3
"""Valida a imagem multi-linguagem nas mesmas restrições da tentativa.

Fase 1, sem rede: versões e um servidor HTTP mínimo por linguagem, só com biblioteca padrão.
Fase 2, com proxy: instalação de um pacote pequeno por ecossistema, liberando apenas os
registros listados, e bloqueio de um domínio fora da lista. Não usa credenciais.
"""
import argparse
import json
import secrets
import subprocess
import sys

REGISTRIES = ['pypi.org', 'files.pythonhosted.org', 'registry.npmjs.org', 'proxy.golang.org',
              'sum.golang.org', 'repo.maven.apache.org']
HARDENING = ['--init', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
             '--pids-limit', '256', '--memory', '2g', '--cpus', '2',
             '--tmpfs', '/tmp:rw,nosuid,nodev,exec,size=512m',
             '--tmpfs', '/home/agent:rw,nosuid,nodev,exec,uid=1001,gid=1001,mode=700,size=1g',
             '--tmpfs', '/workspace:rw,nosuid,nodev,exec,uid=1001,gid=1001,mode=700,size=512m']

OFFLINE = r'''
set -u
cd /workspace
fail=0
check() { name=$1; shift; if out=$("$@" 2>&1); then echo "PASS $name: $(echo "$out" | tail -1)"; else echo "FAIL $name: $(echo "$out" | tail -3 | tr '\n' ' ')"; fail=1; fi; }
serve() { # nome, porta, comando em background; espera resposta HTTP 200
  name=$1; port=$2; shift 2
  "$@" > /tmp/$name.log 2>&1 & pid=$!
  for i in $(seq 1 60); do
    if code=$(curl -s -o /dev/null -w '%{http_code}' --noproxy '*' http://127.0.0.1:$port/); then [ "$code" = 200 ] && break; fi
    sleep 0.5
  done
  if [ "${code:-}" = 200 ]; then echo "PASS http-$name"; else echo "FAIL http-$name: $(tail -3 /tmp/$name.log | tr '\n' ' ')"; fail=1; fi
  kill $pid 2>/dev/null; wait $pid 2>/dev/null
  return 0
}
check python python3 --version
check venv sh -c 'python3 -m venv /workspace/venv && /workspace/venv/bin/pip --version'
check sqlite-py python3 -c 'import sqlite3; print(sqlite3.sqlite_version)'
check node node --version
check npm npm --version
check node-sqlite node -e 'const {DatabaseSync}=require("node:sqlite"); const d=new DatabaseSync(":memory:"); console.log(d.prepare("select 1 as x").get().x)'
check go go version
check java java --version
check javac javac --version
check maven mvn --version
check gcc gcc --version
check claude claude --version
check codex codex --version
check codex-code-mode-host test -x /usr/local/bin/codex-code-mode-host
check opencode opencode --version
check go-run sh -c 'mkdir -p /workspace/gr && cd /workspace/gr && printf "package main\nfunc main(){println(\"ok\")}\n" > m.go && go run m.go'
check root-readonly sh -c '! touch /usr/local/x 2>/dev/null'
check non-root sh -c 'test "$(id -u)" = 1001'

serve python 8081 python3 -c 'import http.server as h
class H(h.BaseHTTPRequestHandler):
  def do_GET(s): s.send_response(200); s.end_headers(); s.wfile.write(b"ok")
h.ThreadingHTTPServer(("0.0.0.0",8081),H).serve_forever()'
serve node 8082 node -e 'require("http").createServer((q,r)=>r.end("ok")).listen(8082,"0.0.0.0")'
mkdir -p /workspace/gosrv && cd /workspace/gosrv && printf 'package main\nimport "net/http"\nfunc main(){http.HandleFunc("/",func(w http.ResponseWriter,r *http.Request){w.Write([]byte("ok"))});http.ListenAndServe("0.0.0.0:8083",nil)}\n' > main.go && go mod init gosrv >/dev/null 2>&1 && go build -o srv . && cd /workspace && serve go 8083 /workspace/gosrv/srv || { echo "FAIL go-build"; fail=1; }
mkdir -p /workspace/j && printf 'import com.sun.net.httpserver.*;import java.net.*;public class S{public static void main(String[] a)throws Exception{HttpServer s=HttpServer.create(new InetSocketAddress("0.0.0.0",8084),0);s.createContext("/",e->{byte[] b="ok".getBytes();e.sendResponseHeaders(200,b.length);e.getResponseBody().write(b);e.close();});s.start();}}\n' > /workspace/j/S.java && javac -d /workspace/j /workspace/j/S.java && serve java 8084 java -cp /workspace/j S || { echo "FAIL java-build"; fail=1; }
exit $fail
'''

ONLINE = r'''
set -u
cd /workspace
fail=0
check() { name=$1; shift; if out=$("$@" 2>&1); then echo "PASS $name: $(echo "$out" | tail -1)"; else echo "FAIL $name: $(echo "$out" | tail -3 | tr '\n' ' ')"; fail=1; fi; }
check pip sh -c 'python3 -m venv v && v/bin/pip install --no-cache-dir --quiet idna==3.10 && v/bin/python -c "import idna; print(idna.__version__)"'
check npm sh -c 'mkdir n && cd n && npm init -y >/dev/null && npm install --no-audit --no-fund ms@2.1.3 >/dev/null && node -e "console.log(require(\"ms\")(\"1h\"))"'
check go-mod sh -c 'mkdir g && cd g && go mod init g >/dev/null 2>&1 && go get golang.org/x/text@v0.20.0 >/dev/null 2>&1 && go list -m golang.org/x/text'
mkdir -p ~/.m2 && printf '<settings><proxies><proxy><id>p</id><active>true</active><protocol>https</protocol><host>pilot-proxy</host><port>8080</port></proxy></proxies></settings>\n' > ~/.m2/settings.xml
check maven sh -c 'mvn -B -q dependency:get -Dartifact=org.slf4j:slf4j-api:2.0.16 && ls ~/.m2/repository/org/slf4j/slf4j-api/2.0.16/*.jar'
check blocked-host sh -c '! curl -s --max-time 10 -o /dev/null https://github.com'
exit $fail
'''


def docker(*args, check=True, timeout=600, input=None):
    result = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=timeout, input=input)
    if check and result.returncode:
        raise RuntimeError(f'docker {args[0]} falhou: {result.stderr[-1500:]}')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', default='llm-bench-runtime:20260924')
    args = parser.parse_args()
    ok = True
    print('== Fase 1: sem rede')
    offline = docker('run', '--rm', '--network', 'none', *HARDENING, args.image, 'bash', '-c', OFFLINE, check=False)
    print(offline.stdout.strip() or offline.stderr[-1500:])
    ok &= offline.returncode == 0

    print('== Fase 2: proxy com registros de pacotes')
    suffix = secrets.token_hex(3)
    net, proxy = f'llmbench-rtcheck-{suffix}-net', f'llmbench-rtcheck-{suffix}-proxy'
    proxy_env = ['--env', 'HTTPS_PROXY=http://pilot-proxy:8080', '--env', 'HTTP_PROXY=http://pilot-proxy:8080',
                 '--env', 'https_proxy=http://pilot-proxy:8080', '--env', 'http_proxy=http://pilot-proxy:8080',
                 '--env', 'NO_PROXY=localhost,127.0.0.1']
    # O Maven 3.9 ignora HTTPS_PROXY e -Dhttps.proxyHost; o script online grava ~/.m2/settings.xml.
    try:
        docker('network', 'create', '--internal', net)
        docker('run', '-d', '--name', proxy, *HARDENING[:6], '--memory', '256m',
               '--env', 'PILOT_ALLOWED_HOSTS='+','.join(REGISTRIES), args.image, 'python3', '/opt/pilot/proxy.py')
        docker('network', 'connect', '--alias', 'pilot-proxy', net, proxy)
        online = docker('run', '--rm', '--network', net, *HARDENING, *proxy_env, args.image, 'bash', '-c', ONLINE,
                        check=False, timeout=900)
        print(online.stdout.strip() or online.stderr[-1500:])
        ok &= online.returncode == 0
        hosts = sorted({line.split()[1] for line in docker('logs', proxy).stdout.splitlines()
                        if line.startswith(('ALLOW', 'DENY'))})
        print('Destinos vistos pelo proxy (ALLOW/DENY):', json.dumps(hosts))
    finally:
        docker('rm', '-f', proxy, check=False)
        docker('network', 'rm', net, check=False)
    print('RESULTADO:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())

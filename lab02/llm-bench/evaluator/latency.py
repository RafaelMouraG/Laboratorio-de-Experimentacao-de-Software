#!/usr/bin/env python3
"""Diagnóstico de latência (RNF11, M16) de uma entrega congelada do encurtador.

Uso: python3 evaluator/latency.py ENTREGA [--out DIR] [--label NOME] [--config ARQ]

Não é aceitação: não produz veredito nem altera A_i. Reaproveita de evaluate.py o
ambiente limpo (container novo, build com rede só para os registros, servidor sem
rede) e mede, com um gerador de carga em Go (evaluator/loadgen) num container cliente
na mesma rede interna:

  GET /{code}       sobre links semeados antes da medição; válido = 302 e Location igual à url
  POST /api/links   sem alias; válido = 201 com objeto JSON e code

Para cada operação, duas fases por duração, com aquecimento descartado:
  aberta   taxa fixa; latência contada do instante agendado (sem coordinated omission)
  fechada  concorrência fixa (saturação), com teto de requisições
Percentis p50/p90/p95/p99/p99.9 e máximo só das respostas válidas, vazão, taxa de erro,
CPU do servidor por fase (cgroup) e pico de RSS dos processos do servidor (VmHWM).
DATA_DIR fica em disco (volume Docker) ou em tmpfs, conforme o perfil. Servidor e
cliente ficam em conjuntos de CPUs distintos. O perfil está em evaluator/config.json,
seção rnf11_perfil_carga.

Entrega que não compila ou não fica pronta fica sem M16 (ausente, sem valor).
Saída: result.json e summary.txt em .pilot/latency/<run_id>/ (padrão).
Código de saída: 0 medição completa; 1 M16 ausente (entrega não iniciou);
2 falha do instrumento ou erro de uso.
"""
import argparse
import hashlib
import json
import os
import platform
import secrets
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evaluate as ev  # noqa: E402

TOOL_VERSION = "0.2.0"
PREFIX = "llmbench-lat-"
LOADGEN_SRC = HERE / "loadgen" / "main.go"
OPS = ("redirect", "create")

# Executado no container da entrega: CPU do cgroup e memória dos processos do servidor.
PROBE = r'''
import json, os
def cpu_usec():
    for line in open("/sys/fs/cgroup/cpu.stat"):
        k, v = line.split()
        if k == "usage_usec":
            return int(v)
procs = []
for pid in filter(str.isdigit, os.listdir("/proc")):
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode(errors="replace").strip()
        status = dict(l.split(":", 1) for l in open(f"/proc/{pid}/status") if ":" in l)
    except OSError:
        continue
    if not cmd or cmd.startswith(("sleep", "/sbin/docker-init")) or "container_helper" in cmd or "python3 -c" in cmd:
        continue
    kb = lambda k: int(status.get(k, "0 kB").split()[0]) * 1024
    procs.append({"pid": int(pid), "cmd": cmd[:120], "rss": kb("VmRSS"), "hwm": kb("VmHWM"),
                  "threads": int(status.get("Threads", "0").strip() or 0)})
mem = {}
for line in open("/sys/fs/cgroup/memory.stat"):
    k, v = line.split()
    if k in ("anon", "file", "shmem"):
        mem[k] = int(v)
print(json.dumps({"cpu_usec": cpu_usec(), "processes": procs, "memory_current": int(open("/sys/fs/cgroup/memory.current").read()),
                  "memory_stat": mem}))
'''


def loadgen_binary(image, image_id):
    """Compila o gerador de carga uma vez por fonte e imagem, num container sem rede."""
    src = LOADGEN_SRC.read_bytes()
    key = hashlib.sha256(src + image_id.encode()).hexdigest()[:16]
    path = ev.ROOT / ".pilot" / "latency" / "bin" / f"loadgen-{key}"
    if path.exists():
        return path, key
    path.parent.mkdir(parents=True, exist_ok=True)
    name = f"{PREFIX}build-{secrets.token_hex(3)}"
    script = ("mkdir -p /tmp/src && cat > /tmp/src/main.go && cd /tmp/src && "
              "go build -trimpath -o /tmp/loadgen main.go >&2 && cat /tmp/loadgen")
    try:
        r = ev.docker("run", "--rm", "-i", "--name", name, "--network", "none", "--read-only", "--cap-drop", "ALL",
                      "--security-opt", "no-new-privileges", "--tmpfs", "/tmp:rw,exec,size=1g", "-u", "1001",
                      "-e", "HOME=/tmp", "-e", "GOCACHE=/tmp/gocache", "-e", "GOTOOLCHAIN=local", "-e", "CGO_ENABLED=0",
                      image, "sh", "-c", script, input=src, binary=True, timeout=600, check=False)
    finally:
        ev.docker("rm", "-f", name, check=False)
    if r.returncode or not r.stdout:
        raise ev.EvaluatorError(f"compilação do gerador de carga falhou ({r.returncode}): {r.stderr.decode(errors='replace')[-800:]}")
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(r.stdout)
    tmp.chmod(0o755)
    tmp.rename(path)
    return path, key


class LatencyRun(ev.Run):
    def __init__(self, delivery, out_dir, raw_cfg, cfg, label):
        super().__init__(delivery, out_dir, raw_cfg, cfg, label)
        self.base = PREFIX + self.run_id.lower()
        self.net, self.proxy, self.app, self.client = (f"{self.base}-{s}" for s in ("net", "proxy", "app", "client"))
        self.volume = f"{self.base}-data"
        self.profile = raw_cfg["rnf11_perfil_carga"]
        self.on_disk = self.profile["data_dir"]["value"] == "disk"
        self.measurements = []
        self.status = None

    # -- containers ------------------------------------------------------------------
    def setup(self, tar_bytes):
        """Como Run.setup, mas com DATA_DIR num volume em disco quando o perfil pede."""
        if not self.on_disk:
            return super().setup(tar_bytes)
        r = self.res
        ev.docker("volume", "create", self.volume)
        # O volume nasce com dono root; um container de uso único, sem rede, só com CHOWN, o entrega ao UID 1001.
        ev.docker("run", "--rm", "--name", f"{self.base}-chown", "--network", "none", "--read-only", "--cap-drop", "ALL",
                  "--cap-add", "CHOWN", "--user", "0", "-v", f"{self.volume}:/data", self.image, "chown", "1001:1001", "/data")
        ev.docker("network", "create", "--internal", self.net)
        ev.docker("run", "-d", "--name", self.proxy, *self.hardening("256m", 1, 128),
                  "--tmpfs", "/tmp:rw,nosuid,nodev,size=16m",
                  "--env", "PILOT_ALLOWED_HOSTS=" + ",".join(self.raw_cfg["registries"]),
                  self.image, "python3", "/opt/pilot/proxy.py")
        ev.docker("network", "connect", "--alias", ev.PROXY_ALIAS, self.net, self.proxy)
        ev.docker("run", "-d", "--name", self.app, "--network", self.net, "--network-alias", ev.APP_ALIAS,
                  *self.hardening(r["app_memory"], r["app_cpus"], r["app_pids"]),
                  "--tmpfs", f"/tmp:rw,nosuid,nodev,exec,size={r['tmpfs_tmp']}",
                  "--tmpfs", f"/home/agent:rw,nosuid,nodev,exec,uid=1001,gid=1001,mode=700,size={r['tmpfs_home']}",
                  "--tmpfs", f"/workspace:rw,nosuid,nodev,exec,uid=1001,gid=1001,mode=700,size={r['tmpfs_workspace']}",
                  "-v", f"{self.volume}:/data",
                  "--tmpfs", f"/evaluator:rw,nosuid,nodev,uid=1001,gid=1001,mode=700,size={r['tmpfs_evaluator']}",
                  self.image, "sleep", "infinity")
        ev.docker("exec", "-i", self.app, "tar", "-x", "-C", "/workspace", "-f", "-", input=tar_bytes, binary=True, timeout=300)
        ev.docker("exec", "-i", self.app, "sh", "-c", "cat > /evaluator/container_helper.py",
                  input=(HERE / "container_helper.py").read_text())
        settings = (f"<settings><proxies><proxy><id>eval-proxy</id><active>true</active><protocol>https</protocol>"
                    f"<host>{ev.PROXY_ALIAS}</host><port>8080</port><nonProxyHosts>localhost|127.0.0.1</nonProxyHosts>"
                    f"</proxy></proxies></settings>\n")
        ev.docker("exec", "-i", self.app, "sh", "-c", "mkdir -p ~/.m2 && cat > ~/.m2/settings.xml", input=settings)
        fs = ev.docker("exec", self.app, "sh", "-c", "stat -f -c %T /data; df -B1 --output=source,size /data | tail -1", check=False)
        self.diag["data_dir"] = {"mode": "disk (volume Docker)", "volume": self.volume, "fs": fs.stdout.split()}

    def cleanup(self):
        codes = {}
        for name in (self.client, self.app, self.proxy, f"{self.base}-chown"):
            codes[name] = ev.docker("rm", "-f", "-v", name, check=False).returncode
        codes[self.net] = ev.docker("network", "rm", self.net, check=False).returncode
        if self.on_disk:
            codes[self.volume] = ev.docker("volume", "rm", self.volume, check=False).returncode
        left = ev.docker("ps", "-a", "--filter", f"name={self.base}", "--format", "{{.Names}}", check=False).stdout.split()
        left += ev.docker("network", "ls", "--filter", f"name={self.base}", "--format", "{{.Name}}", check=False).stdout.split()
        left += ev.docker("volume", "ls", "--filter", f"name={self.base}", "--format", "{{.Name}}", check=False).stdout.split()
        return {"exit_codes": codes, "leftover": left}

    # -- medição ---------------------------------------------------------------------
    def loadgen(self, params):
        params = {"host": ev.APP_ALIAS, "port": 8080, "timeout_ms": self.profile["request_timeout_ms"],
                  "tag": self.run_id.lower(), **params}
        r = ev.docker("exec", "-i", self.client, "/tmp/loadgen", input=json.dumps(params),
                      timeout=self.profile["phase_timeout_seconds"], check=False)
        if r.returncode:
            raise ev.EvaluatorError(f"loadgen {params['op']}/{params.get('mode')} falhou ({r.returncode}): {r.stderr[-800:]}")
        return json.loads(r.stdout)

    def probe(self):
        return json.loads(ev.docker("exec", self.app, "python3", "-c", PROBE, timeout=60).stdout)

    def alive(self):
        return self.client_call("ready", {"host": ev.APP_ALIAS, "port": 8080}, 3, timeout=30)["ready"]

    def phase(self, op, mode, codes, urls):
        prof = self.profile[mode]
        params = {"op": op, "mode": mode, "warmup_s": prof["warmup_s"], "duration_s": prof["duration_s"],
                  "codes": codes, "urls": urls}
        if mode == "open":
            params.update(rate=prof["rate"], max_inflight=prof["max_inflight"])
        else:
            params.update(concurrency=prof["concurrency"], max_requests=prof["max_requests"])
        before, t0 = self.probe(), time.monotonic()
        m = self.loadgen(params)
        after = self.probe()
        m["phase_seconds"] = round(time.monotonic() - t0, 2)
        cpu_s = (after["cpu_usec"] - before["cpu_usec"]) / 1e6
        total = m.get("valid", 0) + m.get("warmup_valid", 0)
        m["server_cpu"] = {"cpu_seconds": round(cpu_s, 3),
                           "cpu_ms_per_valid_request": round(cpu_s * 1000 / total, 4) if total else None,
                           "nota": "cgroup do container da entrega durante a fase inteira (aquecimento incluído)"}
        return m

    def execute(self, loadgen_path):
        tar_bytes, tree_hash, count, deps = ev.pack_delivery(self.delivery)
        self.diag["delivery"] = {"path": str(self.delivery), "tree_sha256": tree_hash, "entries": count}
        self.diag["dependencies"] = deps
        self.setup(tar_bytes)
        if not self.build():
            self.status = "ausente: build.sh falhou (" + self.req["RNF01"]["summary"] + ")"
            return
        prof = self.profile
        ev.docker("update", "--cpuset-cpus", prof["app_cpuset"], self.app)
        r = self.res
        ev.docker("run", "-d", "--name", self.client, "--network", self.net,
                  *self.hardening(r["client_memory"], prof["client_cpus"], 512), "--cpuset-cpus", prof["client_cpuset"],
                  "--sysctl", "net.ipv4.ip_local_port_range=1024 65535", "--sysctl", "net.ipv4.tcp_tw_reuse=1",
                  "--tmpfs", "/tmp:rw,nosuid,nodev,exec,size=64m", self.image, "sleep", "infinity")
        ev.docker("exec", "-i", self.client, "sh", "-c", "cat > /tmp/checks.py", input=(HERE / "checks.py").read_text())
        ev.docker("exec", "-i", self.client, "sh", "-c", "cat > /tmp/loadgen && chmod 755 /tmp/loadgen",
                  input=loadgen_path.read_bytes(), binary=True)

        s1 = self.start(1)
        self.diag["start"] = s1
        if not s1["ready"]:
            self.status = f"ausente: GET /health não respondeu 200 {self.not_ready(s1)}"
            self.stop(1)
            return
        self.diag["server_idle"] = self.probe()
        seed = self.loadgen({"op": "seed", "concurrency": 4, "requests": prof["seed_links"]})
        codes, urls = seed["codes"], seed["urls"]
        self.diag["seed"] = {"links": len(codes)}
        for op in OPS:
            for mode in ("open", "closed"):
                if not self.alive():
                    self.measurements.append({"op": op, "mode": mode, "skipped": "servidor indisponível antes da fase"})
                    continue
                self.measurements.append(self.phase(op, mode, codes, urls))
            if op == "redirect":
                # Sanidade: cada 302 válido (aquecimento incluído) deve ter somado uma visita (RNF06).
                expected = sum(x.get("valid", 0) + x.get("warmup_valid", 0) for x in self.measurements if x["op"] == "redirect")
                observed = self.loadgen({"op": "visits", "concurrency": 8, "codes": codes, "urls": urls}).get("visits_total")
                self.diag["visits_check"] = {"expected_from_valid_302": expected, "observed_sum": observed,
                                             "ok": observed == expected}
        final = self.probe()
        server = [p for p in final["processes"]]
        self.diag["server_memory"] = {
            "rss_peak_bytes": sum(p["hwm"] for p in server), "rss_current_bytes": sum(p["rss"] for p in server),
            "processes": server, "cgroup_memory_current": final["memory_current"], "cgroup_memory_stat": final["memory_stat"],
            "nota": "rss_peak_bytes soma o VmHWM dos processos do servidor; o cgroup inclui tmpfs e cache de arquivos"}
        du = ev.docker("exec", self.app, "du", "-sb", "/data", check=False).stdout.split()
        self.diag["data_dir_bytes_after"] = int(du[0]) if du and du[0].isdigit() else None
        self.diag["alive_after"] = self.alive()
        self.stop(1)
        self.status = "completa"

    def run(self):
        self.out.mkdir(parents=True, exist_ok=True)
        started_at, t0 = ev.utc_now(), time.monotonic()
        info = json.loads(ev.docker("image", "inspect", self.image).stdout)[0]
        self.diag["image_id"] = info["Id"]
        self.diag["image_rootfs_sha256"] = hashlib.sha256(json.dumps(info["RootFS"]["Layers"]).encode()).hexdigest()
        loadgen_key = None
        try:
            loadgen_path, loadgen_key = loadgen_binary(self.image, info["Id"])
            self.execute(loadgen_path)
        except Exception as e:  # noqa: BLE001 — falha do instrumento, nunca atribuída à entrega
            self.errors.append(f"{type(e).__name__}: {str(e)[:600]}")
        except KeyboardInterrupt:
            self.errors.append("interrompido pelo usuário")
        finally:
            try:
                self.collect_logs()
            except Exception as e:  # noqa: BLE001
                self.errors.append(f"coleta de logs: {e}")
            cleanup = self.cleanup()
        if self.errors:
            self.status = "inconclusiva (falha do instrumento)"
        result = {
            "schema": "llm-bench-latency/0.2", "tool_version": TOOL_VERSION, "requirement": "RNF11", "metric": "M16",
            "acceptance": "não — diagnóstico; não altera A_i",
            "run_id": self.run_id, "label": self.label, "status": self.status,
            "started_at_utc": started_at, "finished_at_utc": ev.utc_now(),
            "duration_seconds": round(time.monotonic() - t0, 2),
            "image": self.image, "profile": self.profile, "loadgen": {"source": "evaluator/loadgen/main.go", "key": loadgen_key},
            "placement": {"app_cpus": self.res["app_cpus"], "app_memory": self.res["app_memory"],
                          "app_cpuset": self.profile["app_cpuset"], "client_cpuset": self.profile["client_cpuset"],
                          "host_cpus": os.cpu_count(), "host_kernel": platform.release(),
                          "data_dir": self.profile["data_dir"]["value"]},
            "base_url": self.base_url,
            "measurements": self.measurements,
            "diagnostics": self.diag, "errors": self.errors, "cleanup": cleanup,
        }
        (self.out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        summary = render(result)
        (self.out / "summary.txt").write_text(summary)
        return result, summary


def render(result):
    d = result["diagnostics"]
    pl = result["placement"]
    lines = [f"Latência {result['run_id']} ({result['label']}) — {result['status']}",
             f"Entrega: árvore sha256 {d.get('delivery', {}).get('tree_sha256', '?')[:16]}…  "
             f"build {d.get('build', {}).get('seconds', '?')} s  prontidão {d.get('start', {}).get('seconds', '?')} s",
             f"Servidor: CPUs {pl['app_cpuset']} ({pl['app_cpus']}), cliente: CPUs {pl['client_cpuset']}; "
             f"DATA_DIR em {pl['data_dir']}", "",
             f"{'operação':<9} {'fase':<18} {'válidas':>8} {'erro':>7} {'p50':>7} {'p99':>7} {'p99.9':>7} {'máx':>8} "
             f"{'req/s':>9} {'CPU ms/req':>10}"]
    for m in result["measurements"]:
        if "skipped" in m:
            lines.append(f"{m['op']:<9} {m['mode']:<18} pulada: {m['skipped']}")
            continue
        lat = m.get("latency_ms") or {}
        cell = lambda k, w=7: f"{lat[k]:>{w}.2f}" if k in lat else f"{'—':>{w}}"  # noqa: E731
        phase = f"aberta {m['target_rate']:.0f}/s" if m["mode"] == "open" else f"fechada c={m['concurrency']}"
        if m.get("capped_by_max_requests"):
            phase += " (teto)"
        cpu = (m.get("server_cpu") or {}).get("cpu_ms_per_valid_request")
        lines.append(f"{m['op']:<9} {phase:<18} {m['valid']:>8} {m['error_rate']:>7.2%} {cell('p50')} {cell('p99')} "
                     f"{cell('p999')} {cell('max', 8)} {m['throughput_valid_rps']:>9.1f} "
                     f"{(f'{cpu:.3f}' if cpu is not None else '—'):>10}")
        if m.get("start_lag_ms"):
            lag = m["start_lag_ms"]
            lines.append(f"          atraso de envio do cliente: p50 {lag['p50']:.3f} ms, p99 {lag['p99']:.3f} ms; "
                         f"tempo de serviço p50 {m['service_ms']['p50']:.2f} ms, p99 {m['service_ms']['p99']:.2f} ms"
                         + (f"; {m['late_starts_over_1ms']} envios com mais de 1 ms de atraso" if m.get('late_starts_over_1ms') else ""))
        if m.get("invalid_samples"):
            lines.append(f"          exemplos fora do contrato: {m['invalid_samples'][:2]}")
    lines.append("latência em ms")
    vc = d.get("visits_check")
    if vc:
        lines += ["", f"Sanidade: visitas somadas {vc['observed_sum']} para {vc['expected_from_valid_302']} redirecionamentos 302 válidos"
                  + (" — ok" if vc["ok"] else " — DIVERGE")]
    sm = d.get("server_memory")
    if sm:
        lines.append(f"Memória do servidor: pico de RSS {sm['rss_peak_bytes'] / 2**20:.1f} MiB; DATA_DIR ao final: "
                     f"{(d.get('data_dir_bytes_after') or 0) / 2**20:.1f} MiB")
    if result["errors"]:
        lines += ["", "Falhas do instrumento:"] + ["  " + e[:300] for e in result["errors"]]
    left = result["cleanup"]["leftover"]
    lines += ["", "Limpeza: " + ("ok, nada restou com o prefixo " + PREFIX if not left else "SOBRARAM " + ", ".join(left))]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("delivery", help="diretório ou tar da entrega congelada")
    parser.add_argument("--config", default=str(HERE / "config.json"))
    parser.add_argument("--out", help="diretório de saída (padrão: .pilot/latency/<run_id>)")
    parser.add_argument("--label", help="rótulo livre registrado no resultado")
    parser.add_argument("--quiet", action="store_true", help="não imprime o resumo")
    args = parser.parse_args(argv)
    if not Path(args.delivery).exists():
        parser.error(f"entrega não encontrada: {args.delivery}")
    raw_cfg, cfg = ev.load_config(args.config)
    if "rnf11_perfil_carga" not in raw_cfg:
        parser.error("configuração sem a seção rnf11_perfil_carga")
    run = LatencyRun(args.delivery, ".", raw_cfg, cfg, args.label or Path(args.delivery).name)
    run.out = Path(args.out) if args.out else ev.ROOT / ".pilot" / "latency" / run.run_id
    result, summary = run.run()
    if not args.quiet:
        print(summary, end="")
        print("Evidências:", run.out)
    if result["status"] == "completa":
        return 0
    return 1 if (result["status"] or "").startswith("ausente") else 2


if __name__ == "__main__":
    sys.exit(main())

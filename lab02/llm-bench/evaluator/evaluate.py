#!/usr/bin/env python3
"""Avaliador automatizado do contrato do encurtador (v0.1) sobre uma entrega congelada.

Uso: python3 evaluator/evaluate.py ENTREGA [--out DIR] [--label NOME] [--config ARQ]

ENTREGA é um diretório ou um tar (.tar, .tar.gz, .tgz…) cuja raiz é a raiz da entrega.
Python 3.11+, só biblioteca padrão; requer Docker e a imagem llm-bench-runtime.

Fluxo (docs/avaliador.md): container novo com raiz somente leitura, UID 1001, sem
capabilities; build.sh com rede só para os registros de pacotes, via proxy; proxy
removido; start.sh sem rede externa; checks a partir de um container cliente na
mesma rede interna; SIGTERM e novo start.sh com o mesmo DATA_DIR (RNF09); SIGTERM,
restauração de tudo menos DATA_DIR ao estado pós-build e novo start.sh (RNF04).
Nenhuma porta é publicada no host. Containers e rede usam o prefixo llmbench-eval-
e são removidos ao final, inclusive em caso de falha.

Saída: result.json e summary.txt no diretório de saída; resumo no stdout.
Código de saída: 0 se A_i = 1; 1 se A_i = 0; 2 se a avaliação ficou inconclusiva
por falha do avaliador ou erro de uso.
"""
import argparse
import hashlib
import io
import json
import posixpath
import secrets
import subprocess
import sys
import tarfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EVALUATOR_VERSION = "0.2.0"
CONTRACT_VERSION = "0.1"
PREFIX = "llmbench-eval-"
PROXY_ALIAS = "eval-proxy"
APP_ALIAS = "app"

REQUIREMENTS = {
    "RNF01": "build.sh conclui com código 0 no ambiente limpo",
    "RNF02": "GET /health responde 200 dentro do prazo de prontidão",
    "RNF03": "funciona sem acesso à rede externa",
    "RNF04": "grava dados persistentes somente em DATA_DIR",
    "RNF05": "short_url usa BASE_URL",
    "RNF06": "não perde visitas sob redirecionamentos simultâneos",
    "RNF07": "um único link entre criações simultâneas com o mesmo alias",
    "RNF08": "códigos distintos sob criações simultâneas sem alias",
    "RNF09": "preserva links, visitas e exclusões após SIGTERM e novo início",
    "RF01": "cria link e responde 201 com o recurso e Location",
    "RF02": "gera códigos de 6 a 12 caracteres de [A-Za-z0-9]",
    "RF03": "cria link com o alias como código",
    "RF04": "redireciona com 302 para a URL original",
    "RF05": "conta uma visita por redirecionamento",
    "RF06": "consulta não conta visita",
    "RF07": "exclui e responde 204",
    "RF08": "aceita expires_at futuro e devolve o mesmo instante",
    "RF09": "410 no redirecionamento de link expirado",
    "RF10": "consulta de link expirado continua respondendo",
    "RF11": "GET /health responde 200",
    "RN01": "422 para url ausente ou não string",
    "RN02": "422 para URL relativa, sem host ou esquema não http(s)",
    "RN03": "aceita 2048 caracteres e rejeita 2049 com 422",
    "RN04": "422 para URL com espaço ou controle",
    "RN05": "esquema sem distinção de maiúsculas",
    "RN06": "422 para alias fora do padrão",
    "RN07": "422 para aliases reservados",
    "RN08": "409 para alias existente",
    "RN09": "409 para alias de link excluído",
    "RN10": "422 para expires_at inválido",
    "RN11": "400 para corpo não JSON ou não objeto",
    "RN12": "404 para código inexistente nas três operações",
    "RN13": "formato de erro e error.code definidos",
    "RN14": "novo link a cada POST, mesmo com URL repetida",
    "RN15": "ignora campos desconhecidos",
}
N_REQUIRED = len(REQUIREMENTS)
PHASE1_IDS = [i for i in REQUIREMENTS if i.startswith(("RF", "RN")) and not i.startswith("RNF")] + ["RNF05", "RNF06", "RNF07", "RNF08"]


class EvaluatorError(Exception):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def docker(*args, input=None, timeout=120, check=True, binary=False, stdout=None):
    kwargs = {"timeout": timeout, "input": input}
    if stdout is not None:
        kwargs.update(stdout=stdout, stderr=subprocess.STDOUT)
    else:
        kwargs["capture_output"] = True
    if not binary:
        kwargs["text"] = True
    result = subprocess.run(["docker", *args], **kwargs)
    if check and result.returncode:
        err = result.stderr if isinstance(result.stderr, str) else (result.stderr or b"").decode(errors="replace")
        raise EvaluatorError(f"docker {' '.join(args[:2])} falhou ({result.returncode}): {err[-1500:]}")
    return result


def load_config(path):
    raw = json.loads(Path(path).read_text())
    values = {k: v["value"] for k, v in raw["contrato"].items()}
    values.update({k: v["value"] for k, v in raw["operacional"].items() if isinstance(v, dict) and "value" in v})
    return raw, values


MANIFESTS = {"package.json", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts", "pyproject.toml",
             "Pipfile", "setup.py", "setup.cfg"}
LOCKS = {"package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "go.sum", "poetry.lock",
         "Pipfile.lock", "uv.lock", "pdm.lock"}
VENDORED = ("node_modules", ".git", ".venv", "venv", "vendor", "target", "__pycache__")


def dependency_profile(members):
    """Manifestos e lockfiles presentes na entrega (diagnóstico C5; sem efeito no veredito)."""
    manifests, locks, pinned = [], [], []
    for info, data in members:
        parts = info.name.split("/")
        if not info.isfile() or any(p in VENDORED for p in parts[:-1]):
            continue
        base = parts[-1]
        if base in MANIFESTS:
            manifests.append(info.name)
        elif base in LOCKS:
            locks.append(info.name)
        elif base.startswith("requirements") and base.endswith(".txt"):
            manifests.append(info.name)
            lines = [l.split("#")[0].strip() for l in (data or b"").decode("utf-8", "replace").splitlines()]
            reqs = [l for l in lines if l and not l.startswith("-")]
            if reqs and all("--hash=" in l for l in reqs):
                locks.append(info.name + " (com --hash)")
            elif reqs and all("==" in l for l in reqs):
                pinned.append(info.name)
    note = None
    if any(m.endswith("pom.xml") for m in manifests):
        note = "Maven não tem lockfile padrão; versões fixas no pom.xml não fixam dependências transitivas por intervalo"
    return {"manifests": manifests, "locks": locks, "pinned_requirements": pinned,
            "has_lock": bool(locks), "note": note}


def pack_delivery(path):
    """Tar sem compressão com a raiz da entrega, e hash da árvore para rastreabilidade."""
    path = Path(path)
    buf, tree = io.BytesIO(), hashlib.sha256()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as dst:
        if path.is_dir():
            members = []
            for p in sorted(path.rglob("*")):
                info = dst.gettarinfo(str(p), arcname=p.relative_to(path).as_posix())
                if info is None:
                    continue
                members.append((info, p.read_bytes() if info.isfile() else None))
        elif path.is_file() and tarfile.is_tarfile(path):
            members = []
            with tarfile.open(path) as src:
                for info in src.getmembers():
                    name = posixpath.normpath(info.name)
                    if name in (".", ""):
                        continue
                    if name.startswith("/") or ".." in Path(name).parts:
                        raise EvaluatorError(f"caminho inseguro no tar: {info.name}")
                    if not (info.isfile() or info.isdir() or info.issym()):
                        continue
                    info.name = name
                    members.append((info, src.extractfile(info).read() if info.isfile() else None))
            members.sort(key=lambda m: m[0].name)
        else:
            raise EvaluatorError(f"entrega não é diretório nem tar: {path}")
        for info, data in members:
            info.uid = info.gid = 1001
            info.uname = info.gname = "agent"
            kind = "f" if info.isfile() else "l" if info.issym() else "d"
            tree.update(f"{kind}\0{info.name}\0{info.mode & 0o111:o}\0".encode())
            if data is not None:
                tree.update(hashlib.sha256(data).digest())
                dst.addfile(info, io.BytesIO(data))
            else:
                tree.update(info.linkname.encode())
                dst.addfile(info)
    return buf.getvalue(), tree.hexdigest(), len(members), dependency_profile(members)


def tail(path_or_text, lines=8, width=300):
    text = path_or_text.read_text(errors="replace") if isinstance(path_or_text, Path) else path_or_text
    return [line[:width] for line in text.strip().splitlines()[-lines:]]


class Run:
    def __init__(self, delivery, out_dir, raw_cfg, cfg, label):
        self.delivery, self.out, self.raw_cfg, self.cfg = Path(delivery), Path(out_dir), raw_cfg, cfg
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
        base = PREFIX + self.run_id.lower()
        self.net, self.proxy, self.app, self.client = (f"{base}-{s}" for s in ("net", "proxy", "app", "client"))
        self.req = {}
        self.diag = {}
        self.label = label
        self.errors = []
        self.image = raw_cfg["image"]
        self.base_url = raw_cfg["base_url"]
        self.res = raw_cfg["operacional"]["resources"]

    # -- veredictos ---------------------------------------------------------------
    def set(self, rid, verdict, summary, evidence=()):
        self.req[rid] = {"verdict": verdict, "summary": summary, "evidence": list(evidence)[:8]}

    def fill_u(self, reason):
        for rid in REQUIREMENTS:
            if rid not in self.req:
                self.set(rid, "U", reason)

    # -- docker ---------------------------------------------------------------------
    def hardening(self, memory, cpus, pids):
        return ["--init", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--pids-limit", str(pids), "--memory", memory, "--cpus", str(cpus)]

    def helper(self, *args, timeout=120):
        r = docker("exec", self.app, "python3", "/evaluator/container_helper.py", *args, timeout=timeout)
        return json.loads(r.stdout)

    def client_call(self, command, params, *args, timeout=None):
        r = docker("exec", "-i", self.client, "python3", "/tmp/checks.py", command, *map(str, args),
                   input=json.dumps(params), timeout=timeout or self.cfg["phase_timeout_seconds"], check=False)
        if r.returncode:
            raise EvaluatorError(f"checks.py {command} falhou ({r.returncode}): {r.stderr[-1500:]}")
        try:
            return json.loads(r.stdout)
        except ValueError:
            raise EvaluatorError(f"checks.py {command} não devolveu JSON: {r.stdout[-500:]}")

    def client_params(self):
        c = self.cfg
        return {"host": APP_ALIAS, "port": 8080, "base_url": self.base_url,
                "request_timeout": c["request_timeout_seconds"], "clock_tolerance": c["clock_tolerance_seconds"],
                "expiry_seconds": c["expiry_seconds"], "expiry_margin": c["expiry_margin_seconds"],
                "n": c["concurrency_n_visits"], "m": c["concurrency_m_alias"], "p": c["concurrency_p_codes"],
                "redirects_k": c["redirects_k"], "code_samples": c["generated_code_samples"]}

    def exit_status(self, n):
        r = docker("exec", self.app, "cat", f"/evaluator/start-{n}.exit", check=False)
        try:
            return json.loads(r.stdout) if r.returncode == 0 else None
        except ValueError:
            return None

    def start(self, n):
        """Inicia start.sh e espera GET /health 200 até o prazo de prontidão."""
        deadline = self.cfg["readiness_seconds"]
        t0 = time.monotonic()
        docker("exec", "-d", "-e", "DATA_DIR=/data", "-e", f"BASE_URL={self.base_url}", "-w", "/workspace",
               self.app, "python3", "/evaluator/container_helper.py", "run", str(n))
        params = {"host": APP_ALIAS, "port": 8080}
        last, exited = None, None
        while True:
            elapsed = time.monotonic() - t0
            if elapsed >= deadline:
                break
            probe = self.client_call("ready", params, min(2.0, deadline - elapsed), timeout=30)
            last = probe["last"]
            if probe["ready"]:
                return {"ready": True, "seconds": round(time.monotonic() - t0, 2), "last": last,
                        "exited_early": self.exit_status(n)}
            exited = self.exit_status(n)
            if exited and exited.get("code") != 0:
                break
        return {"ready": False, "seconds": round(time.monotonic() - t0, 2), "last": last,
                "exited": exited or self.exit_status(n)}

    def not_ready(self, s):
        """Descrição da falha de prontidão, com o código de saída de start.sh quando houver."""
        ex = s.get("exited")
        detail = f"em {self.cfg['readiness_seconds']} s"
        if ex:
            detail = f"(start.sh terminou com código {ex.get('code')} após {s['seconds']} s" + (f": {ex['error']}" if ex.get("error") else "") + ")"
        return detail

    def stop(self, n):
        tol = self.cfg["sigterm_tolerance_seconds"]
        result = self.helper("stop", str(n), str(tol), timeout=tol + 60)
        self.diag.setdefault("sigterm", []).append({"start": n, **result})
        return result

    # -- fases ----------------------------------------------------------------------
    def setup(self, tar_bytes):
        r = self.res
        docker("network", "create", "--internal", self.net)
        docker("run", "-d", "--name", self.proxy, *self.hardening("256m", 1, 128),
               "--tmpfs", "/tmp:rw,nosuid,nodev,size=16m",
               "--env", "PILOT_ALLOWED_HOSTS=" + ",".join(self.raw_cfg["registries"]),
               self.image, "python3", "/opt/pilot/proxy.py")
        docker("network", "connect", "--alias", PROXY_ALIAS, self.net, self.proxy)
        docker("run", "-d", "--name", self.app, "--network", self.net, "--network-alias", APP_ALIAS,
               *self.hardening(r["app_memory"], r["app_cpus"], r["app_pids"]),
               "--tmpfs", f"/tmp:rw,nosuid,nodev,exec,size={r['tmpfs_tmp']}",
               "--tmpfs", f"/home/agent:rw,nosuid,nodev,exec,uid=1001,gid=1001,mode=700,size={r['tmpfs_home']}",
               "--tmpfs", f"/workspace:rw,nosuid,nodev,exec,uid=1001,gid=1001,mode=700,size={r['tmpfs_workspace']}",
               "--tmpfs", f"/data:rw,nosuid,nodev,exec,uid=1001,gid=1001,mode=700,size={r['tmpfs_data']}",
               "--tmpfs", f"/evaluator:rw,nosuid,nodev,uid=1001,gid=1001,mode=700,size={r['tmpfs_evaluator']}",
               self.image, "sleep", "infinity")
        docker("exec", "-i", self.app, "tar", "-x", "-C", "/workspace", "-f", "-", input=tar_bytes, binary=True, timeout=300)
        docker("exec", "-i", self.app, "sh", "-c", "cat > /evaluator/container_helper.py",
               input=(HERE / "container_helper.py").read_text())
        settings = (f"<settings><proxies><proxy><id>eval-proxy</id><active>true</active><protocol>https</protocol>"
                    f"<host>{PROXY_ALIAS}</host><port>8080</port><nonProxyHosts>localhost|127.0.0.1</nonProxyHosts>"
                    f"</proxy></proxies></settings>\n")
        docker("exec", "-i", self.app, "sh", "-c", "mkdir -p ~/.m2 && cat > ~/.m2/settings.xml", input=settings)

    def build(self):
        timeout = self.cfg["build_timeout_seconds"]
        proxy = f"http://{PROXY_ALIAS}:8080"
        env = []
        for name in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"):
            env += ["-e", f"{name}={proxy}"]
        env += ["-e", "NO_PROXY=localhost,127.0.0.1", "-e", "no_proxy=localhost,127.0.0.1"]
        log = self.out / "build.log"
        t0 = time.monotonic()
        with open(log, "wb") as f:
            r = docker("exec", "-w", "/workspace", *env, self.app, "timeout", "-s", "TERM", "-k", "10", str(timeout),
                       "./build.sh", stdout=f, binary=True, timeout=timeout + 60, check=False)
        seconds = round(time.monotonic() - t0, 2)
        proxy_log = docker("logs", self.proxy, check=False)
        (self.out / "proxy.log").write_text(proxy_log.stdout + proxy_log.stderr)
        seen = sorted({" ".join(line.split()[:2]) for line in proxy_log.stdout.splitlines()
                       if line.startswith(("ALLOW", "DENY", "CONNECT_FAILED"))})
        self.diag["build"] = {"exit_code": r.returncode, "seconds": seconds, "proxy_destinations": seen}
        docker("rm", "-f", self.proxy, check=False)
        self.diag["post_build_sweep"] = self.helper("sweep")
        evidence = [f"./build.sh → código {r.returncode} em {seconds} s", f"destinos no proxy: {seen or 'nenhum'}"]
        evidence += ["log: " + line for line in tail(log, 4)]
        if r.returncode == 0:
            self.set("RNF01", "S", f"build.sh terminou com código 0 em {seconds} s", evidence)
        elif r.returncode == 124:
            self.set("RNF01", "U", f"build.sh excedeu o teto operacional de {timeout} s; o contrato não tem prazo de build", evidence)
        else:
            reason = {126: " (build.sh sem permissão de execução)", 127: " (build.sh ausente)"}.get(r.returncode, "")
            self.set("RNF01", "V", f"build.sh terminou com código {r.returncode}{reason}", evidence)
        return r.returncode == 0

    def execute(self):
        tar_bytes, tree_hash, count, deps = pack_delivery(self.delivery)
        self.diag["delivery"] = {"path": str(self.delivery), "tree_sha256": tree_hash, "entries": count}
        self.diag["dependencies"] = deps
        info = json.loads(docker("image", "inspect", self.image).stdout)[0]
        self.diag["image_id"] = info["Id"]
        self.setup(tar_bytes)
        if not self.build():
            self.fill_u(f"Pré-condição RNF01 não satisfeita: build ({self.req['RNF01']['summary']})")
            return

        isolation = self.helper("isolation")
        self.diag["isolation"] = isolation
        snapshot = self.helper("snapshot", timeout=600)
        self.diag["snapshot"] = {"bytes": snapshot["bytes"], "error_count": snapshot["error_count"], "errors": snapshot["errors"]}
        before_listing = snapshot["listing"]

        r = self.res
        docker("run", "-d", "--name", self.client, "--network", self.net,
               *self.hardening(r["client_memory"], 2, 512), "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m",
               self.image, "sleep", "infinity")
        docker("exec", "-i", self.client, "sh", "-c", "cat > /tmp/checks.py", input=(HERE / "checks.py").read_text())

        # Início 1: prontidão e checks funcionais.
        s1 = self.start(1)
        self.diag["start_1"] = s1
        limit = self.cfg["readiness_seconds"]
        if not s1["ready"]:
            self.set("RNF02", "V", f"GET /health não respondeu 200 {self.not_ready(s1)}",
                     [f"última sonda: {s1['last']}"] + ["log de start.sh: " + l for l in self.start_log_tail(1)])
            self.stop(1)
            self.fill_u("Pré-condição RNF02 não satisfeita: o servidor não ficou pronto")
            return
        self.set("RNF02", "S", f"GET /health → 200 em {s1['seconds']} s (prazo {limit} s)", [s1["last"]])
        if s1.get("exited_early"):
            self.diag["start_exited_before_ready"] = s1["exited_early"]

        phase1 = self.client_call("phase1", self.client_params())
        for rid in PHASE1_IDS:
            if rid in phase1["results"]:
                self.req[rid] = phase1["results"][rid]
        if phase1.get("evaluator_errors"):
            self.errors += phase1["evaluator_errors"]
        fixture = phase1["fixture"]
        self.diag["fixture"] = {k: v for k, v in fixture.items() if k != "observed"}

        if isolation["isolated"]:
            self.set("RNF03", "S", "servidor pronto e checks executados sem rota externa; proxy do build removido",
                     [f"{k}: {v}" for k, v in isolation["probes"].items()])
        else:
            self.set("RNF03", "U", "sonda de isolamento encontrou rota externa; execução não prova funcionamento offline",
                     [f"{k}: {v}" for k, v in isolation["probes"].items()])
            self.errors.append("isolamento de rede não confirmado")

        # Início 2: SIGTERM e novo start.sh com o mesmo DATA_DIR (RNF09).
        self.stop(1)
        if fixture.get("incomplete"):
            self.set("RNF09", "U", "Pré-condição não satisfeita: fixture de durabilidade incompleta — " + fixture["incomplete"], fixture.get("log", []))
            self.set("RNF04", "U", "Pré-condição RNF09 não satisfeita (fixture incompleta)")
            return
        check_tombstone = self.req.get("RN09", {}).get("verdict") == "S"
        s2 = self.start(2)
        self.diag["start_2"] = s2
        if not s2["ready"]:
            self.set("RNF09", "V", f"após SIGTERM, novo start.sh com o mesmo DATA_DIR não respondeu /health {self.not_ready(s2)}",
                     [f"última sonda: {s2['last']}"] + ["log de start.sh: " + l for l in self.start_log_tail(2)])
            self.stop(2)
            self.set("RNF04", "U", "Pré-condição RNF09 não satisfeita")
            return
        d2 = self.client_call("durability", {**self.client_params(), "fixture": fixture, "before": fixture["observed"],
                                             "check_tombstone": check_tombstone})
        self.set("RNF09", d2["verdict"], d2["summary"], d2["evidence"])
        self.stop(2)
        if d2["verdict"] != "S":
            self.set("RNF04", "U", "Pré-condição RNF09 não satisfeita: estado não sobreviveu ao reinício simples")
            return

        # Início 3: tudo fora de DATA_DIR volta ao estado pós-build (RNF04).
        after_listing = self.helper("listing", timeout=300)
        self.diag["changed_outside_data_dir"] = diff_listing(before_listing, after_listing)
        restored = self.helper("restore", timeout=600)
        self.diag["restore"] = restored
        if snapshot["error_count"] or restored["errors"]:
            self.set("RNF04", "U", "snapshot ou restauração do estado pós-build incompletos; teste de DATA_DIR não confiável",
                     (snapshot["errors"] + restored["errors"])[:6])
            return
        s3 = self.start(3)
        self.diag["start_3"] = s3
        if not s3["ready"]:
            self.set("RNF04", "U", f"com /workspace, home, /tmp e /dev/shm restaurados ao estado pós-build, o servidor não ficou pronto {self.not_ready(s3)}",
                     [f"última sonda: {s3['last']}"] + ["log de start.sh: " + l for l in self.start_log_tail(3)])
            self.stop(3)
            return
        d3 = self.client_call("durability", {**self.client_params(), "fixture": fixture, "before": d2["observed"],
                                             "check_tombstone": check_tombstone})
        changed = self.diag["changed_outside_data_dir"]
        note = [f"alterados fora de DATA_DIR durante a execução (diagnóstico): {changed['count']}"
                + (f", ex.: {changed['sample'][:3]}" if changed["count"] else "")]
        if d3["verdict"] == "S":
            self.set("RNF04", "S", "estado preservado com apenas DATA_DIR mantido e o resto restaurado ao pós-build", d3["evidence"][:4] + note)
        elif d3["verdict"] == "V":
            self.set("RNF04", "V", "estado sobreviveu ao reinício simples, mas não quando só DATA_DIR foi mantido: " + d3["summary"], d3["evidence"][:4] + note)
        else:
            self.set("RNF04", "U", d3["summary"], d3["evidence"] + note)
        self.stop(3)

    def start_log_tail(self, n):
        r = docker("exec", self.app, "tail", "-n", "5", f"/evaluator/start-{n}.log", check=False)
        return tail(r.stdout or "(vazio)", 5)

    def collect_logs(self):
        for n in (1, 2, 3):
            r = docker("exec", self.app, "sh", "-c", f"test -f /evaluator/start-{n}.log && tail -c 200000 /evaluator/start-{n}.log",
                       check=False, binary=True)
            if r.returncode == 0:
                (self.out / f"start-{n}.log").write_bytes(r.stdout)

    def cleanup(self):
        codes = {}
        for name in (self.client, self.app, self.proxy):
            codes[name] = docker("rm", "-f", "-v", name, check=False).returncode
        codes[self.net] = docker("network", "rm", self.net, check=False).returncode
        base = PREFIX + self.run_id.lower()
        left = docker("ps", "-a", "--filter", f"name={base}", "--format", "{{.Names}}", check=False).stdout.split()
        left += docker("network", "ls", "--filter", f"name={base}", "--format", "{{.Name}}", check=False).stdout.split()
        return {"exit_codes": codes, "leftover": left}

    def evaluate(self):
        self.out.mkdir(parents=True, exist_ok=True)
        started_at, t0 = utc_now(), time.monotonic()
        status = "completa"
        try:
            self.execute()
        except Exception as e:  # noqa: BLE001 — qualquer falha aqui é do avaliador ou da infraestrutura
            detail = traceback.format_exc(limit=3).strip().splitlines()
            self.errors.append(f"{type(e).__name__}: {e} [{' | '.join(detail[-3:])}]")
        except KeyboardInterrupt:
            self.errors.append("interrompido pelo usuário")
        finally:
            try:
                self.collect_logs()
            except Exception as e:  # noqa: BLE001
                self.errors.append(f"coleta de logs: {e}")
            cleanup = self.cleanup()
        if self.errors:
            status = "inconclusiva (falha do avaliador)"
            self.fill_u("Avaliação interrompida ou não confiável por falha do avaliador: " + self.errors[0][:300])
        self.fill_u("Não avaliado")
        ordered = {rid: self.req[rid] for rid in REQUIREMENTS}
        counts = {v: sum(1 for r in ordered.values() if r["verdict"] == v) for v in ("S", "V", "U")}
        result = {
            "schema": "llm-bench-eval/0.1",
            "evaluator_version": EVALUATOR_VERSION,
            "contract_version": CONTRACT_VERSION,
            "run_id": self.run_id,
            "label": self.label,
            "status": status,
            "started_at_utc": started_at,
            "finished_at_utc": utc_now(),
            "duration_seconds": round(time.monotonic() - t0, 2),
            "image": self.image,
            "config": {"base_url": self.base_url, "params": self.cfg,
                       "provisional": "parâmetros do contrato e operacionais provisórios ('provisório — calibrar'); o teto de build é operacional, pois o contrato não tem prazo de build"},
            "counts": {**counts, "N": N_REQUIRED},
            "A_i": 1 if counts["S"] == N_REQUIRED else 0,
            "M3": round(counts["S"] / N_REQUIRED, 4),
            "requirements": ordered,
            "not_evaluated": {"RNF10": "diagnóstico; o tempo até o término após SIGTERM está em diagnostics.sigterm",
                              "RNF11": "stub: perfil de carga não definido", "RNF12": "fora do escopo",
                              "RNF13": "fora do escopo", "RNF14": "fora do escopo"},
            "diagnostics": self.diag,
            "evaluator_errors": self.errors,
            "cleanup": cleanup,
        }
        (self.out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        summary = render_summary(result)
        (self.out / "summary.txt").write_text(summary)
        return result, summary


def diff_listing(before, after):
    b, a = before["entries"], after["entries"]
    changed = sorted(p for p in a if p not in b or (a[p][0] == "f" and a[p] != b[p]))
    removed = sorted(p for p in b if p not in a)
    return {"count": len(changed), "removed": len(removed), "sample": changed[:20], "removed_sample": removed[:10],
            "truncated": before.get("truncated") or after.get("truncated")}


def render_summary(result):
    c = result["counts"]
    lines = [
        f"Avaliação {result['run_id']} ({result['label']}) — {result['status']}",
        f"Entrega: {result['diagnostics'].get('delivery', {}).get('path', '?')}  "
        f"árvore sha256 {result['diagnostics'].get('delivery', {}).get('tree_sha256', '?')[:16]}…",
        f"Imagem: {result['image']} {result['diagnostics'].get('image_id', '')[:19]}",
        f"A_i = {result['A_i']}   S={c['S']} V={c['V']} U={c['U']} N={c['N']}   M3 = S/N = {c['S']}/{c['N']}",
        "",
        f"{'ID':<6} {'':1}  Resumo",
    ]
    for rid, r in result["requirements"].items():
        lines.append(f"{rid:<6} {r['verdict']}  {r['summary'][:150]}")
    if result["evaluator_errors"]:
        lines += ["", "Falhas do avaliador:"] + ["  " + e[:300] for e in result["evaluator_errors"]]
    deps = result["diagnostics"].get("dependencies")
    if deps:
        lines += ["", "Dependências (diagnóstico C5): manifestos " + (", ".join(deps["manifests"]) or "nenhum")
                  + "; lockfiles " + (", ".join(deps["locks"]) or "nenhum")
                  + (f"; requirements fixados sem hash: {', '.join(deps['pinned_requirements'])}" if deps["pinned_requirements"] else "")]
    sig = result["diagnostics"].get("sigterm", [])
    if sig:
        lines += ["", "SIGTERM (diagnóstico RNF10): " + "; ".join(
            f"início {s['start']}: " + ("forçado com SIGKILL" if s.get("forced_kill") else f"terminou em {s.get('group_exit_s', s.get('leader_exit_s', '?'))} s")
            for s in sig)]
    left = result["cleanup"]["leftover"]
    lines += ["", "Limpeza: " + ("ok, nada restou com o prefixo " + PREFIX if not left else "SOBRARAM " + ", ".join(left)),
              "Parâmetros provisórios — calibrar (evaluator/config.json)."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("delivery", help="diretório ou tar da entrega congelada")
    parser.add_argument("--config", default=str(HERE / "config.json"))
    parser.add_argument("--out", help="diretório de saída (padrão: .pilot/eval/<run_id>)")
    parser.add_argument("--label", help="rótulo livre registrado no resultado")
    parser.add_argument("--quiet", action="store_true", help="não imprime o resumo")
    args = parser.parse_args(argv)
    if not Path(args.delivery).exists():
        parser.error(f"entrega não encontrada: {args.delivery}")
    raw_cfg, cfg = load_config(args.config)
    run = Run(args.delivery, ".", raw_cfg, cfg, args.label or Path(args.delivery).name)
    run.out = Path(args.out) if args.out else ROOT / ".pilot" / "eval" / run.run_id
    result, summary = run.evaluate()
    if not args.quiet:
        print(summary, end="")
        print("Evidências:", run.out)
    if result["status"] != "completa":
        return 2
    return 0 if result["A_i"] == 1 else 1


if __name__ == "__main__":
    sys.exit(main())

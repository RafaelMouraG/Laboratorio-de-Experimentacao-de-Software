#!/usr/bin/env python3
"""Runner da coleta: uma tentativa da tarefa do encurtador, congelamento e avaliação.

Uso: python3 scripts/run-attempt.py PARTICIPANTE [--timeout S] [--no-evaluate] [--dry-run]

Uma tentativa por execução, sem repetição automática. O agente roda inteiro num
container novo da imagem multi-linguagem, com as exigências de infra/runtime/README.md:
tmpfs com exec, ~/.m2/settings.xml com o proxy e rede só para os provedores do
participante mais os registros de pacotes. O prompt é a Parte A do contrato, com
os placeholders preenchidos pelos valores provisórios do avaliador. Ao final, o
/workspace é congelado como tar, com hashes, e avaliado por evaluator/evaluate.py
num ambiente limpo. Nenhuma tentativa é oficial enquanto o protocolo não for congelado.

Reaproveita, sem modificar, as credenciais, a redação e a extração de tokens de
scripts/run-pilot.py e o hash de árvore de evaluator/evaluate.py.
"""
import argparse
import hashlib
import importlib.util
import json
import secrets
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "infra/attempt/config.json"
CONTRACT = ROOT / "docs/contrato-encurtador.md"
EVAL_CONFIG = ROOT / "evaluator/config.json"
HELPER = ROOT / "evaluator/container_helper.py"
PREFIX = "llmbench-attempt-"
# run-pilot.py escolhe credencial e formato de consumo pelo nome do participante do piloto;
# aqui a escolha é pelo harness, para que outro modelo no mesmo harness (ex.: astra no Codex)
# use a mesma credencial e o mesmo extrator.
PILOT_NAME_BY_HARNESS = {"claude": "opus", "codex": "sol", "opencode": "muse"}
PROXY_ALIAS = "attempt-proxy"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pilot = load_module("run_pilot", ROOT / "scripts/run-pilot.py")
evaluate = load_module("evaluate", ROOT / "evaluator/evaluate.py")


def docker(*args, input=None, timeout=120, check=True, binary=False):
    result = subprocess.run(["docker", *args], input=input, capture_output=True, text=not binary, timeout=timeout)
    if check and result.returncode:
        err = result.stderr if isinstance(result.stderr, str) else result.stderr.decode(errors="replace")
        raise RuntimeError(f"docker {' '.join(args[:2])} falhou ({result.returncode}): {err[-1500:]}")
    return result


def sha256(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


def render_prompt(cfg):
    """Preâmbulo + Parte A do contrato, com placeholders preenchidos; recusa se sobrar [A DEFINIR]."""
    contract = CONTRACT.read_text()
    start = contract.index("## Parte A")
    end = contract.index("\n---", start)
    part_a = contract[start:end].split("\n", 1)[1].strip()  # sem o título de coordenação
    eval_cfg = json.loads(EVAL_CONFIG.read_text())
    filled = {}
    for old, spec in cfg["prompt"]["placeholders"].items():
        source, key = spec["from"].split(":", 1)
        node = json.loads((ROOT / source).read_text()) if source != "evaluator/config.json" else eval_cfg
        for part in key.split("."):
            node = node[part]
        value = node["value"] if isinstance(node, dict) else node
        if part_a.count(old) != 1:
            raise SystemExit(f"placeholder não encontrado exatamente uma vez na Parte A: {old!r}")
        part_a = part_a.replace(old, spec["template"].format(value=value))
        filled[old] = value
    for forbidden in ("[A DEFINIR]", "Parte B", "reservad"):
        if forbidden in part_a:
            raise SystemExit(f"a Parte A renderizada ainda contém {forbidden!r}; não é seguro enviá-la")
    prompt = cfg["prompt"]["preamble"].strip() + "\n\n" + part_a + "\n"
    return prompt, {"contract_sha256": sha256(contract), "part_a_sha256": sha256(part_a),
                    "prompt_sha256": sha256(prompt), "placeholders": filled}


def harness_files(p, creds):
    files = dict(creds)
    files[".m2/settings.xml"] = (
        "<settings><proxies><proxy><id>attempt-proxy</id><active>true</active><protocol>https</protocol>"
        f"<host>{PROXY_ALIAS}</host><port>8080</port><nonProxyHosts>localhost|127.0.0.1</nonProxyHosts>"
        "</proxy></proxies></settings>\n")
    if p["harness"] == "claude":
        files[".claude.json"] = {"hasCompletedOnboarding": True}
        files[".claude/settings.json"] = {"autoMemoryEnabled": False}
    elif p["harness"] == "opencode":
        files[".config/opencode/opencode.json"] = {
            "autoupdate": False, "share": "disabled", "model": p["model"],
            "enabled_providers": [p["model"].split("/")[0]], "permission": p["permission"]}
    return files


def harness_command(p, prompt):
    if p["harness"] == "claude":
        return ["claude", "-p", prompt, "--model", p["model"], "--effort", p["effort"], "--output-format", "stream-json",
                "--verbose", "--no-session-persistence", "--permission-mode", "dontAsk",
                "--tools", p["tools"], "--allowedTools", p["tools"],
                "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--no-chrome"]
    if p["harness"] == "opencode":
        variant = ["--variant", p["effort"]] if p["effort"] else []
        return ["opencode", "--pure", "run", "--model", p["model"], *variant, "--format", "json", prompt]
    if p["harness"] == "shell":  # só para testar o runner com um --config alternativo; sem modelo
        return list(p["command"])
    if p["harness"] == "codex":
        return ["codex", "--no-daemon", "-a", "never", "exec", "--ignore-user-config", "--ignore-rules",
                "--model", p["model"], "-c", f'model_reasoning_effort="{p["effort"]}"', "--sandbox", "danger-full-access",
                "--skip-git-repo-check", "--ephemeral", "--json", prompt]
    return None


BOOTSTRAP = r'''
import json, os, sys
from pathlib import Path
payload = json.load(sys.stdin)
home = Path("/home/agent")
assert not list(home.iterdir()), "home não começou vazio"
assert not list(Path("/workspace").iterdir()), "workspace não começou vazio"
assert not Path("/home/rafael-moura").exists()
assert not Path("/var/run/docker.sock").exists()
for rel, value in payload.items():
    p = home / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(value if isinstance(value, str) else json.dumps(value))
    p.chmod(0o600)
print(json.dumps({"home_initially_empty": True, "workspace_initially_empty": True, "host_home_absent": True,
                  "docker_socket_absent": True, "uid": os.getuid(), "files": sorted(payload)}))
'''

NETWORK_CHECK = r'''
import json, socket, urllib.error, urllib.request
def fetch(url):
    try:
        urllib.request.urlopen(url, timeout=20)
        return "ok"
    except urllib.error.HTTPError as e:
        return f"http {e.code}"
    except urllib.error.URLError as e:
        return "bloqueado pelo proxy" if "403" in str(e) else f"erro: {e.reason}"
r = {"registro_pypi": fetch("https://pypi.org/simple/idna/"), "dominio_fora_da_lista": fetch("https://example.com")}
try:
    socket.create_connection(("1.1.1.1", 443), timeout=3).close()
    r["saida_direta"] = "conectou"
except OSError:
    r["saida_direta"] = "bloqueada"
r["ok"] = r["registro_pypi"] == "ok" and r["dominio_fora_da_lista"] == "bloqueado pelo proxy" and r["saida_direta"] == "bloqueada"
print(json.dumps(r))
'''


RESOURCES = r'''
import json, os, subprocess
cg = "/sys/fs/cgroup"
def read(name):
    try:
        return open(os.path.join(cg, name)).read().strip()
    except OSError:
        return None
def kv(name, keys=None):
    text = read(name)
    if text is None:
        return None
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and (keys is None or parts[0] in keys):
            out[parts[0]] = int(parts[1]) if parts[1].isdigit() else parts[1]
    return out
def num(name):
    v = read(name)
    return int(v) if v and v.isdigit() else v
io = {}
for line in (read("io.stat") or "").splitlines():
    for field in line.split()[1:]:
        k, _, v = field.partition("=")
        if k in ("rbytes", "wbytes", "rios", "wios") and v.isdigit():
            io[k] = io.get(k, 0) + int(v)
sizes = {}
for root in ("/workspace", "/home/agent", "/tmp"):
    r = subprocess.run(["du", "-sb", root], capture_output=True, text=True)
    sizes[root] = int(r.stdout.split()[0]) if r.returncode == 0 and r.stdout else None
print(json.dumps({
    "memory_peak_bytes": num("memory.peak"), "memory_current_bytes": num("memory.current"),
    "memory_max": read("memory.max"),
    "memory_stat": kv("memory.stat", {"anon", "file", "shmem", "kernel", "sock"}),
    "memory_events": kv("memory.events"),
    "cpu_stat": kv("cpu.stat", {"usage_usec", "user_usec", "system_usec", "nr_periods", "nr_throttled", "throttled_usec"}),
    "pids_peak": num("pids.peak"), "io": io, "disk_usage_bytes": sizes,
    "nota": "cgroup do container inteiro (harness, ferramentas e processos do agente). memory.peak inclui tmpfs (shmem) e cache de arquivos.",
}))
'''


def activity(harness, events):
    """Contagem de ações do agente segundo os eventos do harness; None quando não observável."""
    events = [e for e in events if isinstance(e, dict)]
    tools = {}

    def count(name):
        tools[name] = tools.get(name, 0) + 1

    if harness == "claude":
        for e in events:
            if e.get("type") == "assistant" and isinstance(e.get("message"), dict):
                for block in e["message"].get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        count(str(block.get("name")))
        result = next((e for e in reversed(events) if e.get("type") == "result"), {})
        extra = {"num_turns": result.get("num_turns"), "duration_ms": result.get("duration_ms"),
                 "duration_api_ms": result.get("duration_api_ms"), "permission_denials": len(result.get("permission_denials") or [])}
    elif harness == "opencode":
        errors = 0
        for e in events:
            part = e.get("part") if isinstance(e.get("part"), dict) else {}
            if e.get("type") == "tool_use":
                count(str(part.get("tool")))
                if (part.get("state") or {}).get("status") == "error":
                    errors += 1
        extra = {"steps": sum(1 for e in events if e.get("type") == "step_finish"), "tool_errors": errors}
    elif harness == "codex":
        failed = 0
        for e in events:
            item = e.get("item") if isinstance(e.get("item"), dict) else {}
            if e.get("type") == "item.completed" and item.get("type") not in (None, "agent_message", "reasoning"):
                count(str(item.get("type")))
                if item.get("type") == "command_execution" and item.get("exit_code") not in (0, None):
                    failed += 1
        extra = {"agent_messages": sum(1 for e in events if e.get("type") == "item.completed"
                                       and (e.get("item") or {}).get("type") == "agent_message"),
                 "commands_nonzero_exit": failed}
    else:
        return None
    return {"tool_calls": sum(tools.values()), "by_tool": dict(sorted(tools.items())), **extra}


def walk_reported(events):
    reported, variants, sessions = set(), set(), set()

    def walk(value):
        if isinstance(value, dict):
            for k, v in value.items():
                if k in ("model", "modelID") and isinstance(v, str):
                    reported.add(v)
                if k == "variant" and isinstance(v, str):
                    variants.add(v)
                if k == "modelUsage" and isinstance(v, dict):
                    reported.update(v)
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    for event in events:
        walk(event)
        if isinstance(event, dict) and isinstance(event.get("sessionID"), str):
            sessions.add(event["sessionID"])
    return reported, variants, sessions, walk


SESSION_EXPORT_PATH = "/tmp/llmbench-session-export.json"


def export_opencode_session(agent, session_id):
    """Exporta a sessão do OpenCode para um arquivo no container e o lê de volta.

    Não usar o stdout do export diretamente: no OpenCode 1.18.32, a saída escrita num
    pipe (como a do docker exec) é truncada em 128 KiB, com código 0, e o JSON de uma
    sessão real fica inválido. Escrita num arquivo, sai completa. Devolve (sessão ou
    None, metadados do export).
    """
    meta = {"session_id": session_id, "method": "arquivo no container, lido com cat"}
    try:
        r = docker("exec", agent, "sh", "-c", 'opencode --pure export "$1" > "$2"', "sh", session_id,
                   SESSION_EXPORT_PATH, check=False, timeout=120)
        meta["exit_code"], meta["stderr"] = r.returncode, r.stderr.strip()[-500:] or None
        c = docker("exec", agent, "cat", SESSION_EXPORT_PATH, check=False, timeout=120, binary=True)
    except subprocess.TimeoutExpired as e:
        meta.update(ok=False, error=f"export sem resposta em {e.timeout} s")
        return None, meta
    text = c.stdout.decode(errors="replace") if c.returncode == 0 else ""
    meta["bytes"] = len(c.stdout) if c.returncode == 0 else None
    try:
        session = json.loads(text)
    except ValueError as e:
        meta.update(ok=False, error=f"JSON inválido: {e}"[:200], head=text[:200] or None)
        return None, meta
    meta["ok"] = True
    return session, meta


def harness_end(harness, events):
    """Como o harness terminou, segundo os próprios eventos; None quando não observável.

    output_limit_hit indica término por limite de saída do modelo: 'length' no último
    step_finish do OpenCode, 'max_tokens' no Claude Code. No Codex, o formato não foi
    validado em tentativa real e o campo fica None.
    """
    events = [e for e in events if isinstance(e, dict)]
    if harness == "opencode":
        steps = [e["part"] for e in events if e.get("type") == "step_finish" and isinstance(e.get("part"), dict)]
        if not steps:
            return None
        reasons = {}
        for part in steps:
            reasons[str(part.get("reason"))] = reasons.get(str(part.get("reason")), 0) + 1
        last = steps[-1].get("reason")
        return {"source": "opencode json: reason dos eventos step_finish", "last_reason": last,
                "reasons": reasons, "steps": len(steps), "output_limit_hit": last == "length"}
    if harness == "claude":
        results = [e for e in events if e.get("type") == "result"]
        assistant = [e["message"] for e in events if e.get("type") == "assistant" and isinstance(e.get("message"), dict)]
        if not results and not assistant:
            return None
        result = results[-1] if results else {}
        last_stop = assistant[-1].get("stop_reason") if assistant else None
        stop = result.get("stop_reason")
        return {"source": "claude stream-json: último result e stop_reason da última mensagem do assistente",
                "result_subtype": result.get("subtype"), "is_error": result.get("is_error"), "stop_reason": stop,
                "last_assistant_stop_reason": last_stop, "output_limit_hit": "max_tokens" in (stop, last_stop)}
    if harness == "codex":
        if not events:
            return None
        types = [e.get("type") for e in events]
        return {"source": "codex exec --json: tipos de evento (formato não validado em tentativa real)",
                "last_event_type": types[-1], "turns_completed": types.count("turn.completed"),
                "turns_failed": types.count("turn.failed"), "errors": types.count("error"), "output_limit_hit": None}
    return None


def main():
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config", default=str(CONFIG))
    config_path = Path(pre.parse_known_args()[0].config)
    cfg = json.loads(config_path.read_text())
    eval_raw = json.loads(EVAL_CONFIG.read_text())
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("participant", choices=sorted(cfg["participants"]))
    parser.add_argument("--timeout", type=int, default=cfg["timeout_seconds"]["value"],
                        help="prazo da tentativa em segundos (padrão provisório em infra/attempt/config.json)")
    parser.add_argument("--no-evaluate", action="store_true", help="congela a entrega sem avaliá-la")
    parser.add_argument("--dry-run", action="store_true", help="mostra prompt, rede e comando sem criar containers")
    parser.add_argument("--config", default=str(CONFIG), help="configuração do runner (padrão: infra/attempt/config.json)")
    args = parser.parse_args()
    if not 60 <= args.timeout <= 4 * 3600:
        parser.error("timeout deve estar entre 60 s e 4 h")
    p = cfg["participants"][args.participant]
    prompt, prompt_meta = render_prompt(cfg)
    hosts = sorted(set(p["provider_hosts"]) | set(eval_raw["registries"]))
    command = harness_command(p, prompt)

    if args.dry_run:
        shown = [("<prompt>" if c == prompt else c) for c in command] if command else ["(simulado: copia " + p["source"] + ")"]
        print(json.dumps({"participant": args.participant, "image": cfg["image"], "timeout_seconds": args.timeout,
                          "allowed_hosts": hosts, "command": shown, **prompt_meta}, ensure_ascii=False, indent=2))
        print("\n----- prompt -----\n" + prompt)
        return 0

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + args.participant + "-" + secrets.token_hex(3)
    out = ROOT / ".pilot/attempts" / run_id
    out.mkdir(parents=True, mode=0o700)
    (out / "prompt.md").write_text(prompt)
    base = PREFIX + run_id.lower()
    net, proxy, agent = f"{base}-net", f"{base}-proxy", f"{base}-agent"
    creds = pilot.credentials(PILOT_NAME_BY_HARNESS[p["harness"]]) if p["harness"] in ("claude", "codex") else {}
    redact_values = list(pilot.sensitive_values(creds))

    def redact(text):
        for value in redact_values:
            text = text.replace(value, "[REDACTED]")
        return text

    res = cfg["resources"]
    summary = {"run_id": run_id, "participant": args.participant, "harness": p["harness"], "requested_model": p["model"],
               "effort": p["effort"], "timeout_seconds": args.timeout, "kill_after_seconds": cfg["kill_after_seconds"]["value"],
               "resources": {k: v for k, v in res.items() if k not in ("status", "nota")},
               "config": str(config_path.relative_to(ROOT)) if config_path.is_relative_to(ROOT) else str(config_path),
               "config_sha256": sha256(config_path.read_bytes()), "runner_sha256": sha256(Path(__file__).read_bytes()), "skills": [], "allowed_hosts": hosts, "official_collection": False, "phase": "piloto",
               "prompt": prompt_meta, "started_at_utc": pilot.utc_now(), "errors": [], "warnings": []}
    started = time.monotonic()
    stdout = stderr = ""
    try:
        info = json.loads(docker("image", "inspect", cfg["image"]).stdout)[0]
        summary["image_id"] = info["Id"]
        # Com o armazenamento containerd, o ID é o digest do índice OCI, que muda a cada build por causa
        # da atestação de proveniência; o conteúdo é identificado pelas camadas e pela configuração.
        summary["image_rootfs_sha256"] = sha256(json.dumps(info["RootFS"]["Layers"]))
        summary["image_created"] = info.get("Created")
        docker("network", "create", "--internal", net)
        hardening = ["--init", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges"]
        docker("run", "-d", "--name", proxy, *hardening, "--pids-limit", "256", "--memory", "256m", "--cpus", "1",
               "--tmpfs", "/tmp:rw,nosuid,nodev,size=16m", "--env", "PILOT_ALLOWED_HOSTS=" + ",".join(hosts),
               cfg["image"], "python3", "/opt/pilot/proxy.py")
        docker("network", "connect", "--alias", PROXY_ALIAS, net, proxy)
        url = f"http://{PROXY_ALIAS}:8080"
        env = []
        for name in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"):
            env += ["--env", f"{name}={url}"]
        env += ["--env", "NO_PROXY=localhost,127.0.0.1", "--env", "no_proxy=localhost,127.0.0.1",
                "--env", "DISABLE_AUTOUPDATER=1", "--env", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1"]
        # CMD explícito: o da imagem (sleep 1200) encerraria o container no meio de uma tentativa longa.
        docker("run", "-d", "--name", agent, *hardening, "--network", net, "--pids-limit", str(res["pids"]),
               "--memory", res["memory"], "--cpus", str(res["cpus"]),
               "--tmpfs", f"/tmp:rw,nosuid,nodev,exec,size={res['tmpfs_tmp']}",
               "--tmpfs", f"/home/agent:rw,nosuid,nodev,exec,uid=1001,gid=1001,mode=700,size={res['tmpfs_home']}",
               "--tmpfs", f"/workspace:rw,nosuid,nodev,exec,uid=1001,gid=1001,mode=700,size={res['tmpfs_workspace']}",
               *env, cfg["image"], "sleep", "infinity")
        files = harness_files(p, creds)
        summary["preflight"] = json.loads(docker("exec", "-i", agent, "python3", "-c", BOOTSTRAP, input=json.dumps(files)).stdout)
        summary["network"] = json.loads(docker("exec", agent, "python3", "-c", NETWORK_CHECK, timeout=90).stdout)
        if not summary["network"]["ok"]:
            raise RuntimeError(f"política de rede não confirmada: {summary['network']}")
        if command:
            ver = docker("exec", agent, command[0], "--version", check=False, timeout=60)
            summary["harness_version"] = (ver.stdout or ver.stderr).strip().splitlines()[-1:] or None
            summary["command"] = [("<prompt: prompt.md>" if c == prompt else c) for c in command]

        # Tentativa.
        task_start = time.monotonic()
        summary["task_started_at_utc"] = pilot.utc_now()
        if command:
            kill_after = cfg["kill_after_seconds"]["value"]
            try:
                r = docker("exec", "-w", "/workspace", agent, "timeout", "--signal=TERM", f"--kill-after={kill_after}s",
                           str(args.timeout), *command, timeout=args.timeout + kill_after + 60, check=False)
                stdout, stderr = r.stdout, r.stderr
                summary["exit_code"] = r.returncode
                summary["timed_out"] = r.returncode in (124, 137)
            except subprocess.TimeoutExpired as e:
                stdout = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
                stderr = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
                summary["exit_code"], summary["timed_out"] = None, True
        else:
            src = evaluate.pack_delivery(ROOT / p["source"])[0]
            docker("exec", "-i", agent, "tar", "-x", "-C", "/workspace", "-f", "-", input=src, binary=True)
            summary["exit_code"], summary["timed_out"] = 0, False
        summary["task_finished_at_utc"] = pilot.utc_now()
        summary["task_seconds"] = round(time.monotonic() - task_start, 3)
        (out / "stdout.jsonl").write_text(redact(stdout))
        (out / "stderr.txt").write_text(redact(stderr))

        # Encerra processos deixados pelo agente antes de congelar, para um snapshot estável.
        # Recursos do container da tentativa, antes de encerrar os processos remanescentes.
        res_probe = docker("exec", agent, "python3", "-c", RESOURCES, check=False, timeout=120)
        try:
            summary["resources_observed"] = json.loads(res_probe.stdout)
        except ValueError:
            summary["resources_observed"] = {"error": (res_probe.stderr or "")[-300:]}
        oom = ((summary["resources_observed"] or {}).get("memory_events") or {}).get("oom_kill")
        if oom:
            summary["warnings"].append(f"o limite de memória matou {oom} processo(s) durante a tentativa (oom_kill)")
        sweep = docker("exec", "-i", agent, "python3", "-", "sweep", input=HELPER.read_text(), check=False)
        summary["leftover_processes"] = json.loads(sweep.stdout).get("swept") if sweep.returncode == 0 else sweep.stderr[-300:]

        # Congelamento.
        frozen = docker("exec", agent, "tar", "-c", "-C", "/workspace", "--numeric-owner", ".",
                        binary=True, check=False, timeout=600)
        summary["frozen_at_utc"] = pilot.utc_now()
        tar_path = out / "delivery.tar"
        tar_path.write_bytes(frozen.stdout)
        tar_path.chmod(0o600)
        _, tree, entries, deps = evaluate.pack_delivery(tar_path)
        with tarfile.open(tar_path) as frozen_tar:
            files = sum(1 for m in frozen_tar.getmembers() if m.isfile())
        leaked = [v for v in redact_values if v.encode() in frozen.stdout]
        if not files:
            summary["warnings"].append("entrega sem arquivos: /workspace vazio no congelamento")
        summary["delivery"] = {"tar": "delivery.tar", "tar_sha256": sha256(frozen.stdout), "bytes": len(frozen.stdout),
                               "tree_sha256": tree, "entries": entries, "files": files, "tar_exit_code": frozen.returncode,
                               "tar_warnings": frozen.stderr.decode(errors="replace")[-500:] or None,
                               "dependencies": deps, "contains_credentials": bool(leaked)}
        if leaked:
            summary["errors"].append("a entrega contém valores de credencial; não compartilhar delivery.tar")

        # Evidências do harness.
        events, invalid = [], 0
        lines = [line for line in stdout.splitlines() if line.strip()]
        for line in lines:
            try:
                events.append(json.loads(line))
            except ValueError:
                invalid += 1
        summary["stdout_lines"] = {"total": len(lines), "not_json": invalid}
        if command and p["harness"] != "shell" and lines:
            try:
                json.loads(lines[-1])
            except ValueError:
                summary["warnings"].append("a última linha do stdout do harness não é JSON; saída possivelmente truncada")
        if command:
            summary["harness_end"] = harness_end(p["harness"], events)
            end = summary["harness_end"] or {}
            if end.get("output_limit_hit"):
                reason = end.get("last_reason") or end.get("stop_reason") or end.get("last_assistant_stop_reason")
                summary["warnings"].append(f"o harness terminou depois de uma resposta interrompida pelo limite de saída do modelo ({reason})")
        reported, variants, sessions, walk = walk_reported(events)
        init = next((e for e in events if isinstance(e, dict) and e.get("type") == "system" and e.get("subtype") == "init"), None)
        if init:  # configuração efetiva anunciada pelo Claude Code; nomes de ferramenta inválidos são ignorados por ele
            summary["harness_init"] = {k: init.get(k) for k in ("tools", "model", "permissionMode", "mcp_servers", "skills",
                                                                 "agents", "plugins", "claude_code_version")}
            requested = set(p.get("tools", "").split(","))
            if set(init.get("tools") or []) != requested:
                summary["tools_mismatch"] = {"requested": sorted(requested), "effective": sorted(init.get("tools") or [])}
        if p["harness"] == "opencode":
            if len(sessions) == 1:
                session, export_meta = export_opencode_session(agent, next(iter(sessions)))
                if export_meta.get("stderr"):
                    export_meta["stderr"] = redact(export_meta["stderr"])
                if export_meta.get("head"):
                    export_meta["head"] = redact(export_meta["head"])
                summary["session_export"] = export_meta
                summary["session_exported"] = session is not None
                if session is not None:
                    walk(session)
                    (out / "session.json").write_text(redact(json.dumps(session, ensure_ascii=False)))
            else:
                summary["session_exported"] = False
                summary["session_export"] = {"ok": False, "error": f"{len(sessions)} sessões no stdout; esperado 1"}
            if not summary["session_exported"]:
                summary["warnings"].append("sessão do OpenCode não exportada; modelo e variante servidos sem registro: "
                                           + str(summary["session_export"].get("error")))
        summary["activity"] = activity(p["harness"], events) if command else None
        summary["reported_models"] = sorted(reported)
        summary["reported_variants"] = sorted(variants)
        try:
            summary["usage"] = (pilot.usage_from_events(PILOT_NAME_BY_HARNESS[p["harness"]], events)
                                if command and p["harness"] in PILOT_NAME_BY_HARNESS else None)
        except Exception as e:  # noqa: BLE001
            summary["usage"], summary["usage_error"] = None, redact(str(e))
    except Exception as e:  # noqa: BLE001
        summary["errors"].append(redact(f"{type(e).__name__}: {e}"))
    finally:
        logs = docker("logs", proxy, check=False)
        (out / "proxy.log").write_text(redact((logs.stdout or "") + (logs.stderr or "")))
        summary["proxy_destinations"] = sorted({" ".join(l.split()[:2]) for l in (logs.stdout or "").splitlines()
                                                 if l.startswith(("ALLOW", "DENY", "CONNECT_FAILED"))})
        codes = {n: docker("rm", "-f", n, check=False).returncode for n in (agent, proxy)}
        codes[net] = docker("network", "rm", net, check=False).returncode
        left = docker("ps", "-a", "--filter", f"name={base}", "--format", "{{.Names}}", check=False).stdout.split()
        left += docker("network", "ls", "--filter", f"name={base}", "--format", "{{.Name}}", check=False).stdout.split()
        summary["cleanup"] = {"exit_codes": codes, "leftover": left}
        summary["attempt_seconds"] = round(time.monotonic() - started, 3)

    # Avaliação em ambiente limpo, depois de descartar o container da tentativa.
    if not args.no_evaluate and "delivery" in summary:
        r = subprocess.run([sys.executable, str(ROOT / "evaluator/evaluate.py"), str(out / "delivery.tar"),
                            "--out", str(out / "eval"), "--label", run_id, "--quiet"], capture_output=True, text=True)
        try:
            result = json.loads((out / "eval/result.json").read_text())
            summary["evaluation"] = {"status": result["status"], "A_i": result["A_i"], "counts": result["counts"],
                                     "M3": result["M3"], "evaluator_version": result["evaluator_version"],
                                     "run_id": result["run_id"], "result": "eval/result.json",
                                     "violated": [k for k, v in result["requirements"].items() if v["verdict"] == "V"],
                                     "inconclusive": [k for k, v in result["requirements"].items() if v["verdict"] == "U"]}
        except (OSError, ValueError, KeyError):
            summary["evaluation"] = None
            summary["errors"].append(f"avaliação sem resultado (saída {r.returncode}): {r.stderr[-500:]}")
    summary["finished_at_utc"] = pilot.utc_now()
    summary["total_seconds"] = round(time.monotonic() - started, 3)
    summary["ok"] = not summary["errors"] and not summary["cleanup"]["leftover"] and "delivery" in summary
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    brief = {k: summary.get(k) for k in ("run_id", "participant", "exit_code", "timed_out", "task_seconds", "evaluation",
                                         "errors", "warnings", "cleanup", "ok")}
    brief["delivery"] = {k: summary.get("delivery", {}).get(k) for k in ("tree_sha256", "entries", "files", "bytes",
                                                                         "contains_credentials")}
    print(json.dumps(brief, ensure_ascii=False, indent=2))
    print("Evidências locais:", out)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

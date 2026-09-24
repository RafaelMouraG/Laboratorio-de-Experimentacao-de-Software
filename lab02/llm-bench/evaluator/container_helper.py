#!/usr/bin/env python3
"""Auxiliar do avaliador dentro do container da entrega (Python 3.11, só stdlib).

Copiado para /evaluator antes da execução; não contém os checks. Subcomandos:
  run N              supervisiona ./start.sh em nova sessão; grava pid, log e saída
  stop N TOLERANCIA  SIGTERM ao grupo de processos de start.sh; SIGKILL após a tolerância
  sweep              mata processos remanescentes da entrega (fora do grupo)
  snapshot           guarda /workspace, $HOME, /tmp e /dev/shm; imprime a listagem
  listing            imprime a listagem atual das mesmas raízes
  restore            apaga essas raízes e restaura o snapshot (DATA_DIR fica intacto)
  isolation          confirma que não há rota para fora da rede interna
"""
import json
import os
import signal
import socket
import stat
import subprocess
import sys
import tarfile
import time

STATE = "/evaluator"
ROOTS = ["/workspace", "/home/agent", "/tmp", "/dev/shm"]
SNAPSHOT = os.path.join(STATE, "snapshot.tar")
LISTING_LIMIT = 50000


def out(value):
    print(json.dumps(value, ensure_ascii=False))


def pid_file(n):
    return os.path.join(STATE, f"start-{n}.pid")


def exit_file(n):
    return os.path.join(STATE, f"start-{n}.exit")


def cmd_run(n):
    log = open(os.path.join(STATE, f"start-{n}.log"), "wb")
    started = time.time()
    try:
        child = subprocess.Popen(["./start.sh"], cwd="/workspace", stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    except OSError as e:
        result = {"code": 127 if isinstance(e, FileNotFoundError) else 126, "error": str(e),
                  "t": time.time(), "started": started}
        with open(exit_file(n), "w") as f:
            json.dump(result, f)
        return
    with open(pid_file(n), "w") as f:
        f.write(str(child.pid))
    code = child.wait()
    with open(exit_file(n), "w") as f:
        json.dump({"code": code, "t": time.time(), "started": started}, f)


def processes():
    """(pid, ppid, pgid, cmdline) de todos os processos visíveis."""
    result = []
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat") as f:
                raw = f.read()
            fields = raw[raw.rindex(")") + 2:].split()
            state, ppid, pgid = fields[0], int(fields[1]), int(fields[2])
            with open(f"/proc/{name}/cmdline", "rb") as f:
                cmd = f.read().replace(b"\0", b" ").decode(errors="replace").strip()
        except (OSError, ValueError):
            continue
        if state != "Z":
            result.append((int(name), ppid, pgid, cmd))
    return result


def protected_pids():
    """PID 1 (init), o sleep principal, este processo e seus ancestrais, e supervisores."""
    procs = processes()
    keep = {1, os.getpid()}
    parent = os.getppid()
    while parent > 1:
        keep.add(parent)
        try:
            with open(f"/proc/{parent}/stat") as f:
                raw = f.read()
            parent = int(raw[raw.rindex(")") + 2:].split()[1])
        except (OSError, ValueError):
            break
    for pid, ppid, _, cmd in procs:
        if (ppid == 1 and cmd.startswith("sleep")) or "container_helper.py" in cmd:
            keep.add(pid)
    return keep


def sweep():
    keep = protected_pids()
    killed = []
    for pid, _, _, cmd in processes():
        if pid not in keep:
            try:
                os.kill(pid, signal.SIGKILL)
                killed.append(cmd[:200] or str(pid))
            except OSError:
                pass
    deadline = time.time() + 5
    while time.time() < deadline and any(p not in keep for p, *_ in processes()):
        time.sleep(0.05)
    return killed


def port_open(port=8080):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def cmd_stop(n, tolerance):
    result = {"signal": "SIGTERM ao grupo de processos de start.sh", "tolerance_s": tolerance}
    if os.path.exists(exit_file(n)):
        result["already_exited"] = True
    try:
        pgid = int(open(pid_file(n)).read())
    except (OSError, ValueError):
        pgid = None
    t0 = time.time()
    if pgid and not result.get("already_exited"):
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            pass

        def group_alive():
            return any(g == pgid for _, _, g, _ in processes())

        while time.time() - t0 < tolerance:
            if os.path.exists(exit_file(n)) and "leader_exit_s" not in result:
                result["leader_exit_s"] = round(time.time() - t0, 3)
            if os.path.exists(exit_file(n)) and not group_alive():
                result["group_exit_s"] = round(time.time() - t0, 3)
                break
            time.sleep(0.05)
        else:
            result["forced_kill"] = True
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            deadline = time.time() + 5
            while time.time() < deadline and not os.path.exists(exit_file(n)):
                time.sleep(0.05)
    try:
        result["exit"] = json.load(open(exit_file(n)))
    except (OSError, ValueError):
        result["exit"] = None
    result["swept"] = sweep()
    result["port_8080_still_open"] = port_open()
    out(result)


def iter_files(root, errors=None):
    def failed(e):
        if errors is not None:
            errors.append(f"{e.filename}: {e.strerror}")

    for base, dirs, files in os.walk(root, onerror=failed):
        dirs.sort()
        for name in sorted(dirs + files):
            yield os.path.join(base, name)


def listing():
    entries, truncated = {}, False
    for root in ROOTS:
        for path in iter_files(root):
            if len(entries) >= LISTING_LIMIT:
                truncated = True
                break
            try:
                st = os.lstat(path)
            except OSError:
                continue
            kind = "d" if stat.S_ISDIR(st.st_mode) else "l" if stat.S_ISLNK(st.st_mode) else "f"
            entries[path] = [kind, st.st_size if kind == "f" else 0, st.st_mtime_ns if kind == "f" else 0]
    return {"entries": entries, "truncated": truncated}


def cmd_snapshot():
    """Entrada por entrada, para que um arquivo ilegível vire erro registrado, e não falha geral."""
    errors = []
    with tarfile.open(SNAPSHOT, "w") as tar:
        for root in ROOTS:
            for path in iter_files(root, errors):
                try:
                    tar.add(path, arcname=path.lstrip("/"), recursive=False)
                except OSError as e:
                    errors.append(f"{path}: {e}")
    out({"bytes": os.path.getsize(SNAPSHOT), "errors": errors[:20], "error_count": len(errors), "listing": listing()})


def make_writable(root):
    for base, dirs, _ in os.walk(root):
        for name in dirs:
            path = os.path.join(base, name)
            try:
                if not os.path.islink(path):
                    os.chmod(path, os.lstat(path).st_mode | stat.S_IRWXU)
            except OSError:
                pass


def cmd_restore():
    errors = []
    for root in ROOTS:
        make_writable(root)
        for name in os.listdir(root):
            path = os.path.join(root, name)
            try:
                if os.path.isdir(path) and not os.path.islink(path):
                    subprocess.run(["rm", "-rf", "--", path], check=True, capture_output=True)
                else:
                    os.unlink(path)
            except (OSError, subprocess.CalledProcessError) as e:
                errors.append(f"{path}: {e}")
    with tarfile.open(SNAPSHOT) as tar:
        tar.extractall("/")
    remaining = listing()
    out({"errors": errors[:20], "entries": len(remaining["entries"])})


def cmd_isolation():
    probes = {}
    for label, host in (("ip_externo_1.1.1.1:443", "1.1.1.1"), ("pypi.org:443", "pypi.org"),
                        ("proxy_do_build", "eval-proxy")):
        port = 8080 if host == "eval-proxy" else 443
        try:
            with socket.create_connection((host, port), timeout=3):
                probes[label] = "conectou"
        except OSError as e:
            probes[label] = "bloqueado: " + type(e).__name__
    out({"probes": probes, "isolated": all(v.startswith("bloqueado") for v in probes.values())})


def main(argv):
    command = argv[1]
    if command == "run":
        cmd_run(argv[2])
    elif command == "stop":
        cmd_stop(argv[2], float(argv[3]))
    elif command == "sweep":
        out({"swept": sweep(), "port_8080_still_open": port_open()})
    elif command == "snapshot":
        cmd_snapshot()
    elif command == "listing":
        out(listing())
    elif command == "restore":
        cmd_restore()
    elif command == "isolation":
        cmd_isolation()
    else:
        raise SystemExit(f"subcomando desconhecido: {command}")


if __name__ == "__main__":
    main(sys.argv)

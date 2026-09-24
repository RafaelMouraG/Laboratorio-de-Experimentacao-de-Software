#!/usr/bin/env python3
"""Controles do avaliador: referência, variante positiva e variantes quebradas.

Cada variante é gerada por substituições textuais em evaluator/reference/. Toda
substituição precisa casar exatamente uma vez, para que uma mudança na referência
não gere um controle silenciosamente inválido. Um controle passa quando o conjunto
de requisitos V e o de requisitos U são exatamente os esperados, A_i é o esperado,
a avaliação termina completa e nada sobra com o prefixo llmbench-eval-.

Uso: python3 evaluator/controls.py [--only NOME ...] [--jobs N] [--out DIR] [--list]
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from evaluate import REQUIREMENTS  # noqa: E402

ALL = set(REQUIREMENTS)
VALIDATION_422 = {"RN01", "RN02", "RN03", "RN04", "RN06", "RN07", "RN10"}

REGISTRY_BUILD = '''#!/bin/sh
# Variante positiva: exercita os quatro registros de pacotes pelo proxy do avaliador.
set -eu
cd "$(dirname "$0")"
python3 -m py_compile app.py
python3 -m venv .venv
.venv/bin/pip install --no-cache-dir --quiet idna==3.10
mkdir -p .probe/npm .probe/go
(cd .probe/npm && npm init -y >/dev/null && npm install --no-audit --no-fund --silent ms@2.1.3)
(cd .probe/go && go mod init probe >/dev/null 2>&1 && go get golang.org/x/text@v0.20.0)
mvn -B -q dependency:get -Dartifact=org.slf4j:slf4j-api:2.0.16
'''

# nome: (descrição, V esperado, U esperado, A_i esperado, [(arquivo, antigo, novo)])
CONTROLS = {
    "referencia": ("Implementação de referência sem alterações", set(), set(), 1, []),
    "referencia-registros": (
        "Referência com build.sh que baixa de PyPI, npm, proxy Go e Maven Central e start.sh que usa o venv",
        set(), set(), 1,
        [("build.sh", None, REGISTRY_BUILD),
         ("start.sh", "exec python3 app.py", '.venv/bin/python -c "import idna"\nexec .venv/bin/python app.py')]),
    "referencia-start-sem-exec": (
        "Referência com start.sh que mantém o shell como pai do Python (sem exec)", set(), set(), 1,
        [("start.sh", "exec python3 app.py", "python3 app.py")]),
    "build-arquivo-ilegivel": (
        "build.sh deixa um arquivo sem permissão de leitura; snapshot incompleto deixa RNF04 inconclusivo",
        set(), {"RNF04"}, 0,
        [("build.sh", "python3 -m py_compile app.py\n", "python3 -m py_compile app.py\ntouch .ilegivel && chmod 000 .ilegivel\n")]),
    "redirect-301": ("Redireciona com 301 em vez de 302", {"RF04"}, set(), 0,
                     [("app.py", "REDIRECT_STATUS = 302", "REDIRECT_STATUS = 301")]),
    "visitas-perdidas": (
        "Incremento de visitas por leitura e escrita separadas, sem exclusão mútua", {"RNF06"}, set(), 0,
        [("app.py",
          '            self.db.execute("UPDATE links SET visits = visits + 1 WHERE code = ?", (code,))\n',
          '            current = self.db.execute("SELECT visits FROM links WHERE code = ?", (code,)).fetchone()[0]\n'
          '            self.lock.release()\n'
          '            time.sleep(0.02)\n'
          '            self.lock.acquire()\n'
          '            self.db.execute("UPDATE links SET visits = ? WHERE code = ?", (current + 1, code))\n')]),
    "alias-reutilizavel": ("Exclusão apaga a linha, e o alias volta a ficar livre", {"RN09"}, set(), 0,
                           [("app.py", '"UPDATE links SET deleted = 1 WHERE code = ? AND deleted = 0"',
                             '"DELETE FROM links WHERE code = ? AND deleted = 0"')]),
    "sem-persistencia": ("Banco SQLite em memória", {"RNF09"}, {"RNF04"}, 0,
                         [("app.py", 'DB_PATH = os.path.join(DATA_DIR, "links.sqlite3")', 'DB_PATH = ":memory:"')]),
    "reinicio-falha": ("Não reinicia com o mesmo DATA_DIR (CREATE TABLE sem IF NOT EXISTS)", {"RNF09"}, {"RNF04"}, 0,
                       [("app.py", '"CREATE TABLE IF NOT EXISTS links ("', '"CREATE TABLE links ("')]),
    "dados-fora-de-data-dir": ("Banco gravado no diretório de trabalho, fora de DATA_DIR", {"RNF04"}, set(), 0,
                               [("app.py", 'DB_PATH = os.path.join(DATA_DIR, "links.sqlite3")',
                                 'DB_PATH = os.path.join(os.getcwd(), "links.sqlite3")')]),
    "formato-de-erro": ("Erro plano: {\"error\": código, \"message\": …}", {"RN13"}, set(), 0,
                        [("app.py", 'self._send(status, {"error": {"code": code, "message": message}})',
                          'self._send(status, {"error": code, "message": message})')]),
    "validacao-400": ("400 em vez de 422 nos erros de validação", VALIDATION_422, set(), 0,
                      [("app.py", "VALIDATION_STATUS = 422", "VALIDATION_STATUS = 400")]),
    "base-url-ignorada": ("short_url sempre com http://localhost:8080", {"RNF05"}, set(), 0,
                          [("app.py", 'BASE_URL = os.environ.get("BASE_URL") or "http://localhost:8080"',
                            'BASE_URL = "http://localhost:8080"')]),
    "expiracao-ignorada": ("Nunca responde 410", {"RF09"}, set(), 0,
                           [("app.py", 'if row["expires_ts"] is not None and time.time() >= row["expires_ts"]:',
                             "if False:")]),
    "sem-health": ("GET /health responde 404 (rota em /healthz)", {"RNF02"}, ALL - {"RNF01", "RNF02"}, 0,
                   [("app.py", 'if path == "/health":', 'if path == "/healthz":')]),
    "build-falha": ("build.sh termina com código 1", {"RNF01"}, ALL - {"RNF01"}, 0,
                    [("build.sh", "python3 -m py_compile app.py\n", "python3 -m py_compile app.py\nexit 1\n")]),
    "alias-corrida": (
        "Criação com alias por verificação seguida de gravação, sem exclusão mútua", {"RNF07"}, set(), 0,
        [("app.py",
          "                if not self._insert(code, url, created, expires):\n"
          "                    raise Conflict()\n",
          '                exists = self.db.execute("SELECT 1 FROM links WHERE code = ?", (code,)).fetchone()\n'
          "                self.lock.release()\n"
          "                time.sleep(0.05)\n"
          "                self.lock.acquire()\n"
          "                if exists:\n"
          "                    raise Conflict()\n"
          '                self.db.execute("DELETE FROM links WHERE code = ?", (code,))\n'
          "                self._insert(code, url, created, expires)\n")]),
    "codigos-repetidos": (
        "Código gerado a partir de um contador lido sem exclusão mútua; colisão sobrescreve", {"RNF08"}, set(), 0,
        [("app.py",
          "        for _ in range(50):\n"
          '            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))\n'
          "            if self._insert(code, url, created, expires):\n"
          "                return code\n"
          '        raise ApiError(500, "internal_error", "não foi possível gerar um código livre")\n',
          '        count = self.db.execute("SELECT COUNT(*) FROM links").fetchone()[0]\n'
          "        self.lock.release()\n"
          "        time.sleep(0.05)\n"
          "        self.lock.acquire()\n"
          '        code = "c%07d" % count\n'
          '        self.db.execute("DELETE FROM links WHERE code = ?", (code,))\n'
          "        self._insert(code, url, created, expires)\n"
          "        return code\n")]),
    "codigo-curto": ("Códigos gerados com 5 caracteres", {"RF02"}, set(), 0,
                     [("app.py", "CODE_LENGTH = 8", "CODE_LENGTH = 5")]),
    "campos-desconhecidos-rejeitados": ("422 para qualquer campo fora de url, alias e expires_at", {"RN15"}, set(), 0,
                                        [("app.py", '        url = validate_url(data.get("url"))\n',
                                          '        if set(data) - {"url", "alias", "expires_at"}:\n'
                                          '            raise validation("campo desconhecido")\n'
                                          '        url = validate_url(data.get("url"))\n')]),
    "fuso-perdido": ("expires_at devolvido com o horário local rotulado como UTC", {"RF08"}, set(), 0,
                     [("app.py", "    value = value.astimezone(timezone.utc)\n",
                       "    value = value.replace(tzinfo=timezone.utc)\n")]),
    "json-invalido-422": ("422 em vez de 400 para corpo inválido, mantendo error.code invalid_json", {"RN11"}, set(), 0,
                          [("app.py", 'raise ApiError(400, "invalid_json", "corpo não é JSON válido")',
                            'raise ApiError(422, "invalid_json", "corpo não é JSON válido")'),
                           ("app.py", 'raise ApiError(400, "invalid_json", "corpo deve ser um objeto JSON")',
                            'raise ApiError(422, "invalid_json", "corpo deve ser um objeto JSON")')]),
    "queda-com-json-invalido": (
        "Processo encerra ao receber JSON inválido; checks seguintes ficam sem servidor", {"RN11"},
        {"RN12", "RN13", "RN14", "RN15", "RNF06", "RNF07", "RNF08", "RNF09", "RNF04", "RF09", "RF10"}, 0,
        [("app.py", 'raise ApiError(400, "invalid_json", "corpo não é JSON válido")', "os._exit(1)")]),
    "delete-200": ("DELETE responde 200 com corpo", {"RF07"}, set(), 0,
                   [("app.py", "return self._send(204)", 'return self._send(200, {"deleted": True})')]),
    "esquema-sensivel": ("Esquema comparado com distinção de maiúsculas", {"RN05"}, set(), 0,
                         [("app.py", 'if parts.scheme.lower() not in ("http", "https"):',
                           'if url.split(":", 1)[0] not in ("http", "https"):')]),
    "limite-url-2000": ("Limite de URL em 2000 caracteres", {"RN03"}, set(), 0,
                        [("app.py", "MAX_URL_LENGTH = 2048", "MAX_URL_LENGTH = 2000")]),
}


def materialize(name, target):
    """Copia a referência para target e aplica as substituições do controle."""
    shutil.copytree(HERE / "reference", target, ignore=shutil.ignore_patterns("__pycache__", "data"))
    for filename, old, new in CONTROLS[name][4]:
        path = target / filename
        if old is None:
            path.write_text(new)
            continue
        text = path.read_text()
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"{name}: substituição em {filename} casou {count} vezes: {old[:80]!r}")
        path.write_text(text.replace(old, new))
    return target


def run_control(name, workdir, outroot):
    delivery = materialize(name, workdir / name)
    out = outroot / name
    proc = subprocess.run([sys.executable, str(HERE / "evaluate.py"), str(delivery), "--out", str(out),
                           "--label", "controle:" + name, "--quiet"], capture_output=True, text=True, timeout=3600)
    try:
        result = json.loads((out / "result.json").read_text())
    except (OSError, ValueError):
        return {"name": name, "passed": False, "error": f"sem result.json (saída {proc.returncode}): {proc.stderr[-800:]}"}
    _, exp_v, exp_u, exp_a, _ = CONTROLS[name]
    reqs = result["requirements"]
    got_v = {r for r, v in reqs.items() if v["verdict"] == "V"}
    got_u = {r for r, v in reqs.items() if v["verdict"] == "U"}
    checks = {
        "V exato": got_v == exp_v,
        "U exato": got_u == exp_u,
        "A_i": result["A_i"] == exp_a,
        "avaliação completa": result["status"] == "completa",
        "limpeza": not result["cleanup"]["leftover"],
    }
    return {"name": name, "passed": all(checks.values()), "checks": checks,
            "expected_V": sorted(exp_v), "got_V": sorted(got_v), "expected_U": len(exp_u), "got_U": sorted(got_u),
            "counts": result["counts"], "A_i": result["A_i"], "run_id": result["run_id"],
            "duration_seconds": result["duration_seconds"], "out": str(out),
            "violations": {r: reqs[r]["summary"] for r in sorted(got_v)}}


def main():
    parser = argparse.ArgumentParser(description="Executa os controles do avaliador")
    parser.add_argument("--only", nargs="*", help="nomes dos controles (padrão: todos)")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--out", help="diretório de saída (padrão: .pilot/eval/controls-<UTC>)")
    parser.add_argument("--list", action="store_true", help="lista os controles e sai")
    args = parser.parse_args()
    if args.list:
        for name, (desc, v, u, a, _) in CONTROLS.items():
            print(f"{name:<34} V={sorted(v) or '—'} U={len(u)} A_i={a}  {desc}")
        return 0
    names = list(dict.fromkeys(args.only or CONTROLS))  # sem repetição: cada controle usa um diretório próprio
    unknown = [n for n in names if n not in CONTROLS]
    if unknown:
        parser.error(f"controles desconhecidos: {unknown}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    outroot = Path(args.out) if args.out else ROOT / ".pilot" / "eval" / f"controls-{stamp}"
    outroot.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="llmbench-controls-") as tmp:
        with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            results = list(pool.map(lambda n: run_control(n, Path(tmp), outroot), names))
    width = max(len(n) for n in names)
    print(f"{'Controle':<{width}}  Resultado  S/V/U   V obtido")
    for r in results:
        if "error" in r:
            print(f"{r['name']:<{width}}  ERRO       {r['error']}")
            continue
        c = r["counts"]
        failed = [k for k, ok in r["checks"].items() if not ok]
        status = "passou" if r["passed"] else "FALHOU (" + ", ".join(failed) + ")"
        print(f"{r['name']:<{width}}  {status:<9}  {c['S']}/{c['V']}/{c['U']}  {', '.join(r['got_V']) or '—'}")
    passed = sum(r["passed"] for r in results)
    print(f"\n{passed} de {len(results)} controles passaram. Evidências: {outroot}")
    (outroot / "summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

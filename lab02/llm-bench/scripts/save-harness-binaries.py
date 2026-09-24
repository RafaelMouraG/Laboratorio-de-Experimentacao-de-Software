#!/usr/bin/env python3
"""Salva em disco os binários dos harnesses de uma imagem validada e confere seus hashes.

Uso:
  python3 scripts/save-harness-binaries.py                      # extrai e confere contra o manifesto
  python3 scripts/save-harness-binaries.py --write-manifest     # cria o manifesto a partir da imagem
  python3 scripts/save-harness-binaries.py --save-image         # também exporta a imagem (docker save, gzip)

Os binários vão para .pilot/harness-bin/ (ignorado pelo Git). O manifesto versionado,
infra/runtime/harnesses.json, fixa nome, versão, SHA-256 e tamanho. O build da imagem da
coleta (scripts/build-pilot.py --harness-dir) só aceita binários que batam com ele, para
que uma atualização automática no host não troque a versão de um harness sem aviso.
"""
import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "infra/runtime/harnesses.json"
NAMES = ("claude", "codex", "codex-code-mode-host", "opencode")
VERSION_CMD = {"claude": ["claude", "--version"], "codex": ["codex", "--version"], "opencode": ["opencode", "--version"]}


def run(*args, **kw):
    return subprocess.run(args, capture_output=True, text=True, check=True, **kw)


def sha256_file(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--image", default="llm-bench-runtime:20260924")
    parser.add_argument("--out", default=str(ROOT / ".pilot/harness-bin"))
    parser.add_argument("--write-manifest", action="store_true", help="grava o manifesto a partir da imagem")
    parser.add_argument("--save-image", action="store_true", help="exporta a imagem com docker save e gzip")
    args = parser.parse_args()
    image_id = run("docker", "image", "inspect", "--format", "{{.Id}}", args.image).stdout.strip()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    name = "llmbench-savebin-" + hashlib.sha256(image_id.encode()).hexdigest()[:6]
    found = {}
    try:
        run("docker", "create", "--name", name, args.image)
        for binary in NAMES:
            with tempfile.TemporaryDirectory() as tmp:
                run("docker", "cp", f"{name}:/usr/local/bin/{binary}", tmp)
                src = Path(tmp) / binary
                dst = out / binary
                shutil.copy2(src, dst)
                dst.chmod(0o755)
            found[binary] = {"sha256": sha256_file(out / binary), "bytes": (out / binary).stat().st_size}
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    for binary, cmd in VERSION_CMD.items():
        r = subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", cmd[0], args.image, *cmd[1:]],
                           capture_output=True, text=True)
        found[binary]["version"] = (r.stdout or r.stderr).strip().splitlines()[-1]

    if args.write_manifest:
        manifest = {"_nota": "Binários dos harnesses da imagem da coleta. O build só aceita arquivos com estes hashes "
                             "(scripts/build-pilot.py --harness-dir). Gerado por scripts/save-harness-binaries.py.",
                    "extracted_from": {"image": args.image, "image_id": image_id,
                                       "date_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")},
                    "binaries": found}
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        print("Manifesto gravado:", MANIFEST.relative_to(ROOT))
    else:
        expected = json.loads(MANIFEST.read_text())["binaries"]
        bad = [b for b in NAMES if expected.get(b, {}).get("sha256") != found[b]["sha256"]]
        if bad:
            raise SystemExit(f"hash diferente do manifesto: {', '.join(bad)} (imagem {image_id})")
        print("Binários conferem com o manifesto.")
    for binary in NAMES:
        print(f"  {binary:<22} {found[binary]['sha256'][:16]}…  {found[binary]['bytes']:>11} B  {found[binary].get('version', '')}")
    print("Salvos em:", out)

    if args.save_image:
        target = ROOT / ".pilot/images" / f"{args.image.replace('/', '_').replace(':', '_')}-{image_id.split(':')[1][:12]}.tar.gz"
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with subprocess.Popen(["docker", "save", args.image], stdout=subprocess.PIPE) as proc, \
                gzip.open(target, "wb", compresslevel=6) as gz:
            for chunk in iter(lambda: proc.stdout.read(1 << 20), b""):
                digest.update(chunk)
                gz.write(chunk)
        if proc.returncode:
            raise SystemExit(f"docker save falhou ({proc.returncode})")
        (target.parent / (target.name + ".sha256")).write_text(
            f"{sha256_file(target)}  {target.name}\n# sha256 do tar descomprimido (docker save): {digest.hexdigest()}\n"
            f"# imagem: {args.image} {image_id}\n")
        print("Imagem exportada:", target, f"({target.stat().st_size / 1e9:.2f} GB)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Constrói a imagem sem incluir configuração, credenciais ou código de projetos."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', default='llm-bench-pilot:20260924')
    parser.add_argument('--dockerfile', default='infra/pilot/Dockerfile',
                        help='relativo à raiz; ex.: infra/runtime/Dockerfile para a imagem multi-linguagem')
    parser.add_argument('--harness-dir',
                        help='binários fixos (scripts/save-harness-binaries.py), conferidos contra '
                             'infra/runtime/harnesses.json; obrigatório para a imagem da coleta')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    dockerfile = (root/args.dockerfile).resolve()
    if root not in dockerfile.parents or not dockerfile.is_file():
        raise SystemExit(f'Dockerfile inválido: {args.dockerfile}')
    runtime = dockerfile == root/'infra/runtime/Dockerfile'
    if runtime and not args.harness_dir:
        raise SystemExit('a imagem da coleta exige --harness-dir com os binários fixos '
                         '(python3 scripts/save-harness-binaries.py); o build não copia mais do host')
    pinned = json.loads((root/'infra/runtime/harnesses.json').read_text())['binaries'] if args.harness_dir else None
    private = root/'.pilot'
    private.mkdir(exist_ok=True)
    manifest = {}
    with tempfile.TemporaryDirectory(prefix='llm-bench-build-') as temp:
        stage = Path(temp)
        if pinned is not None:
            for name, spec in pinned.items():
                source = Path(args.harness_dir)/name
                if not source.is_file():
                    raise SystemExit(f'Binário fixo ausente: {source}')
                with source.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                if digest != spec['sha256']:
                    raise SystemExit(f'{name}: SHA-256 {digest} difere do manifesto ({spec["sha256"]})')
                shutil.copy2(source, stage/name)
                manifest[name] = {'sha256': digest, 'bytes': source.stat().st_size, 'version': spec.get('version'),
                                  'source': 'harness-dir (fixo)'}
        for name in (() if pinned is not None else ('claude', 'codex', 'opencode')):
            executable = shutil.which(name)
            if not executable:
                raise SystemExit(f'Executável ausente: {name}')
            source = Path(executable).resolve()
            shutil.copy2(source, stage/name)
            with source.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            manifest[name] = {'sha256': digest, 'bytes': source.stat().st_size}
            if name == 'codex':
                # O Codex executa as ferramentas por um auxiliar que fica na mesma pasta de release;
                # sem ele, nenhuma chamada de ferramenta roda (tentativa 20260924T192934Z-sol-9d4b81).
                helper = source.parent/'codex-code-mode-host'
                if not helper.is_file():
                    raise SystemExit(f'Auxiliar do Codex ausente: {helper}')
                shutil.copy2(helper, stage/helper.name)
                with helper.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                manifest[helper.name] = {'sha256': digest, 'bytes': helper.stat().st_size}
        shutil.copy2(dockerfile, stage/'Dockerfile')
        shutil.copy2(root/'infra/pilot/proxy.py', stage/'proxy.py')
        subprocess.run(['docker', 'build', '--tag', args.image, str(stage)], check=True)
    image_id = subprocess.run(['docker', 'image', 'inspect', '--format', '{{.Id}}', args.image],
                              capture_output=True, text=True, check=True).stdout.strip()
    if dockerfile == root/'infra/pilot/Dockerfile':
        (private/'binaries.json').write_text(json.dumps(manifest, indent=2)+'\n')
        (private/'image-id.txt').write_text(image_id+'\n')
    record = {'image': args.image, 'image_id': image_id, 'dockerfile': str(dockerfile.relative_to(root)),
              'dockerfile_sha256': hashlib.sha256(dockerfile.read_bytes()).hexdigest(), 'binaries': manifest}
    images = private/'images'
    images.mkdir(exist_ok=True)
    (images/(args.image.replace('/', '_').replace(':', '_')+'.json')).write_text(json.dumps(record, indent=2)+'\n')
    print('Imagem construída:', image_id)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Cronometragem de um trial — RQ1 (Issue #40).

Mede o "time-to-green" de um trial: o tempo, em segundos, desde o início até que
TODOS os testes de aceitação do kata passem. Se o time-box de 35 min (2100 s) for
atingido antes disso, o trial é encerrado e registrado como *censurado* — nunca
descartado (descartar distorce a comparação a favor do tratamento com mais falhas).

O resultado é gravado como uma linha no CSV de coleta, cujo contrato (cabeçalho e
colunas) está definido na Issue #39: `lab02/data/schema.md` e
`lab02/data/trials_template.csv`. Este script preenche apenas as colunas de tempo e
testes (mais `num_prompts`); as colunas de métricas estáticas (`cc_media`, `loc`,
`duplicacao_pct`, `mi`) ficam vazias e são preenchidas pelo script da Issue #41.

Como funciona
-------------
Durante o trial, o participante escreve a solução no diretório do kata. Este script
roda a suíte de testes do kata em intervalos regulares (`--poll`) e cronometra até:
  - todos os testes passarem  -> `tempo_s` = tempo decorrido, `censurado_35min=false`;
  - o time-box ser atingido    -> `tempo_s` = 2100, `censurado_35min=true`, gravando
                                  quantos testes passavam naquele momento.

Uso
---
    python lab02/src/cronometragem.py \
        --integrante mateusdsoc --kata k1 --tratamento com_ia --ordem 1 \
        --kata-dir lab02/katas/k1

    # com contagem de prompts (só faz sentido em com_ia):
    ... --num-prompts 7

O `--kata-dir` deve conter os testes de aceitação (pytest) e o código da solução.
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

TIMEBOX_PADRAO = 2100  # 35 min em segundos — só pode ser reduzido, nunca aumentado.

RAIZ = Path(__file__).resolve().parents[2]
TEMPLATE_CSV = RAIZ / "lab02" / "data" / "trials_template.csv"
SAIDA_PADRAO = RAIZ / "lab02" / "data" / "trials.csv"


def carregar_colunas() -> list[str]:
    """Lê o cabeçalho do contrato (#39) para garantir que gravamos as colunas certas."""
    if TEMPLATE_CSV.exists():
        with TEMPLATE_CSV.open(encoding="utf-8") as fh:
            cabecalho = fh.readline().strip()
        if cabecalho:
            return cabecalho.split(",")
    # Fallback: mesma ordem do schema.md, caso o template não seja encontrado.
    return [
        "integrante", "kata", "tratamento", "ordem", "tempo_s", "censurado_35min",
        "testes_total", "testes_passando", "taxa_sucesso", "cc_media", "loc",
        "duplicacao_pct", "mi", "num_prompts",
    ]


def rodar_testes(kata_dir: Path) -> tuple[int, int]:
    """Roda a suíte pytest do kata e devolve (total, passando) via JUnit XML.

    Usa `--junitxml` (nativo do pytest, sem plugin) para uma leitura robusta, em vez
    de parsear o texto da saída, que muda entre versões.
    """
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
        relatorio = Path(tmp.name)
    try:
        subprocess.run(
            [sys.executable, "-m", "pytest", str(kata_dir),
             f"--junitxml={relatorio}", "-q", "--no-header"],
            cwd=str(kata_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return _ler_junit(relatorio)
    finally:
        relatorio.unlink(missing_ok=True)


def _ler_junit(relatorio: Path) -> tuple[int, int]:
    """Extrai (total, passando) do JUnit XML. Erros de coleta contam como não-passando."""
    if not relatorio.exists() or relatorio.stat().st_size == 0:
        return (0, 0)
    raiz = ET.parse(relatorio).getroot()
    # A raiz pode ser <testsuites> (com <testsuite> dentro) ou já um <testsuite>.
    suites = raiz.findall("testsuite") or ([raiz] if raiz.tag == "testsuite" else [])
    total = falhas = erros = pulados = 0
    for s in suites:
        total += int(s.get("tests", 0))
        falhas += int(s.get("failures", 0))
        erros += int(s.get("errors", 0))
        pulados += int(s.get("skipped", 0))
    passando = total - falhas - erros - pulados
    return (total, passando)


def cronometrar(kata_dir: Path, timebox: int, poll: float) -> dict:
    """Loop de cronometragem até o green ou o time-box. Devolve as métricas do trial."""
    inicio = time.monotonic()
    total = passando = 0
    while True:
        total, passando = rodar_testes(kata_dir)
        decorrido = time.monotonic() - inicio
        verde = total > 0 and passando == total
        if verde:
            return {
                "tempo_s": round(decorrido),
                "censurado": False,
                "total": total,
                "passando": passando,
            }
        if decorrido >= timebox:
            return {
                "tempo_s": timebox,
                "censurado": True,
                "total": total,
                "passando": passando,
            }
        # Não ultrapassar o time-box no último sono.
        restante = timebox - (time.monotonic() - inicio)
        if restante <= 0:
            continue
        time.sleep(min(poll, restante))


def gravar_linha(saida: Path, colunas: list[str], dados: dict) -> None:
    """Anexa uma linha ao CSV de coleta, criando o cabeçalho se o arquivo não existir."""
    saida.parent.mkdir(parents=True, exist_ok=True)
    novo = not saida.exists()
    with saida.open("a", newline="", encoding="utf-8") as fh:
        # lineterminator="\n": Lab02 padroniza CSV em LF (Unix), igual ao template do #39.
        escritor = csv.DictWriter(fh, fieldnames=colunas, extrasaction="ignore", lineterminator="\n")
        if novo:
            escritor.writeheader()
        # Colunas não preenchidas por este script (métricas do #41) saem vazias.
        linha = {c: dados.get(c, "") for c in colunas}
        escritor.writerow(linha)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cronometragem de um trial (RQ1, Issue #40).")
    parser.add_argument("--integrante", required=True, help="login do GitHub de quem executa o trial")
    parser.add_argument("--kata", required=True, help="id do kata (ex.: k1)")
    parser.add_argument("--tratamento", required=True, choices=["com_ia", "sem_ia"],
                        help="uso ou não do assistente de IA")
    parser.add_argument("--ordem", required=True, type=int, help="posição do trial na sequência do integrante")
    parser.add_argument("--kata-dir", required=True, type=Path, help="diretório com o código e os testes do kata")
    parser.add_argument("--timebox", type=int, default=TIMEBOX_PADRAO,
                        help=f"time-box em segundos (padrão {TIMEBOX_PADRAO}; só pode ser reduzido)")
    parser.add_argument("--poll", type=float, default=5.0, help="intervalo em segundos entre execuções da suíte")
    parser.add_argument("--num-prompts", type=int, default=None,
                        help="nº de prompts/interações com a IA (opcional; só em com_ia)")
    parser.add_argument("--out", type=Path, default=SAIDA_PADRAO, help="CSV de coleta de saída")
    args = parser.parse_args(argv)

    if args.timebox > TIMEBOX_PADRAO:
        parser.error(f"--timebox não pode ser maior que {TIMEBOX_PADRAO}s (regra do enunciado).")
    if not args.kata_dir.is_dir():
        parser.error(f"--kata-dir não é um diretório: {args.kata_dir}")

    colunas = carregar_colunas()
    print(f"Cronometrando {args.kata} · {args.tratamento} · {args.integrante} "
          f"(time-box {args.timebox}s, poll {args.poll}s)...")

    r = cronometrar(args.kata_dir, args.timebox, args.poll)
    taxa = round(r["passando"] / r["total"], 4) if r["total"] else 0.0

    dados = {
        "integrante": args.integrante,
        "kata": args.kata,
        "tratamento": args.tratamento,
        "ordem": args.ordem,
        "tempo_s": r["tempo_s"],
        "censurado_35min": "true" if r["censurado"] else "false",
        "testes_total": r["total"],
        "testes_passando": r["passando"],
        "taxa_sucesso": taxa,
        "num_prompts": args.num_prompts if args.num_prompts is not None else "",
    }
    gravar_linha(args.out, colunas, dados)

    estado = f"CENSURADO no time-box ({r['tempo_s']}s)" if r["censurado"] else f"green em {r['tempo_s']}s"
    print(f"  {estado} — {r['passando']}/{r['total']} testes (taxa {taxa}). Linha gravada em {args.out}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

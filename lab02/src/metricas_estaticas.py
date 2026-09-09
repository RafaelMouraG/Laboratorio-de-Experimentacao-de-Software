#!/usr/bin/env python3
"""Métricas estáticas de um trial — RQ3 (Issue #41).

Roda as ferramentas de análise estática sobre o **código final** de um trial e grava
as colunas de estrutura no CSV de coleta:

| Coluna | Ferramenta | O que é |
|---|---|---|
| `cc_media` | `radon cc` | complexidade ciclomática média por função/método |
| `loc` | `radon raw` | linhas de código (controle **obrigatório** da RQ3) |
| `mi` | `radon mi` | índice de manutenibilidade |
| `duplicacao_pct` | `jscpd` | % de linhas duplicadas |

O contrato do CSV (cabeçalho e colunas) está na Issue #39: `lab02/data/schema.md` e
`lab02/data/trials_template.csv`. O script de cronometragem (RQ1, Issue #40) já grava
a linha do trial com as colunas de tempo/testes; este script **atualiza essa mesma
linha**, casando por `integrante` + `kata` + `tratamento` — não cria uma segunda.

O que entra na medição
----------------------
Só o **código produzido pelo participante**: os testes de aceitação vêm prontos com o
kata e não são obra do trial, então `test_*.py`, `*_test.py`, `conftest.py` e diretórios
`tests/` ficam de fora. Os arquivos selecionados são copiados para um diretório
temporário e todas as ferramentas rodam sobre ele, garantindo que `radon` e `jscpd`
enxerguem exatamente o mesmo conjunto de arquivos.

Decisões de medição (as mesmas em todos os trials, para manter a comparabilidade):
  - `cc_media` é a média sobre funções, métodos e closures. O bloco agregado da classe
    é ignorado: sua complexidade é a soma dos métodos, que já entram na conta à parte.
  - `loc` usa o `sloc` do `radon raw` (linhas de código de fato, sem linhas em branco
    nem comentários), somado sobre os arquivos de solução.
  - `mi` é a média por arquivo ponderada por `sloc` — o MI é calculado por arquivo, e a
    ponderação evita que um arquivo minúsculo pese igual ao arquivo principal.
  - `duplicacao_pct` usa limiares menores que o padrão do jscpd (`--min-lines 5`,
    `--min-tokens 30`), porque soluções de kata são curtas e o padrão (50 tokens) não
    enxergaria clones reais nesse tamanho.

Uso
---
    # um trial
    python lab02/src/metricas_estaticas.py \
        --integrante mateusdsoc --kata k1 --tratamento com_ia \
        --kata-dir lab02/trials/mateusdsoc/k1/com_ia

    # todos os trials de uma vez (runner)
    python lab02/src/metricas_estaticas.py --lote

O modo `--lote` varre `lab02/trials/<integrante>/<kata>/<tratamento>/` — o código final
de cada trial precisa ser arquivado nesse layout ao fim do trial, senão o trial seguinte
sobrescreve o anterior e a medição se perde.

Requer `radon` (no `requirements.txt`) e `jscpd` (`npm install -g jscpd`). Sem o jscpd,
o script segue e deixa apenas `duplicacao_pct` vazia.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from cronometragem import SAIDA_PADRAO, carregar_colunas

RAIZ = Path(__file__).resolve().parents[2]
TRIALS_PADRAO = RAIZ / "lab02" / "trials"

TRATAMENTOS = ("com_ia", "sem_ia")
COLUNAS_METRICAS = ("cc_media", "loc", "duplicacao_pct", "mi")

# Limiares do jscpd — fixos para todos os trials (ver docstring).
JSCPD_MIN_LINES = 5
JSCPD_MIN_TOKENS = 30

# Fora da medição: os testes de aceitação não são código produzido no trial.
ARQUIVOS_IGNORADOS = {"conftest.py", "setup.py"}
DIRS_IGNORADOS = {"__pycache__", ".pytest_cache", "tests", "test", ".git", ".venv", "venv"}


# --------------------------------------------------------------------------- seleção


def arquivos_solucao(kata_dir: Path) -> list[Path]:
    """Arquivos .py escritos pelo participante — sem testes, cache ou diretórios ocultos."""
    selecionados = []
    for caminho in sorted(kata_dir.rglob("*.py")):
        partes = caminho.relative_to(kata_dir).parts
        if any(p in DIRS_IGNORADOS or p.startswith(".") for p in partes[:-1]):
            continue
        nome = caminho.name
        if nome in ARQUIVOS_IGNORADOS or nome.startswith("test_") or nome.endswith("_test.py"):
            continue
        selecionados.append(caminho)
    return selecionados


# ----------------------------------------------------------------------------- radon


def _radon(subcomando: str, alvo: Path) -> dict:
    """Roda `radon <subcomando> -j` e devolve o JSON (mapa arquivo -> resultado)."""
    proc = subprocess.run(
        [sys.executable, "-m", "radon", subcomando, "-j", str(alvo)],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        detalhe = proc.stderr.strip() or "sem saída"
        raise RuntimeError(f"radon {subcomando} falhou: {detalhe}")
    return json.loads(proc.stdout)


def _funcoes(entradas: list[dict]):
    """Achata funções e métodos do `radon cc`, descendo nas closures.

    O bloco `type == "class"` é pulado: a complexidade da classe é a soma dos métodos,
    que o radon já lista à parte no nível de cima — contar os dois duplicaria.
    """
    for bloco in entradas:
        if bloco.get("type") != "class":
            yield bloco
        yield from _funcoes(bloco.get("closures", []))


def complexidade_media(alvo: Path, avisos: list[str]) -> float | None:
    """Complexidade ciclomática média por função/método (`radon cc`)."""
    complexidades: list[int] = []
    for arquivo, entradas in _radon("cc", alvo).items():
        if isinstance(entradas, dict):  # arquivo que o radon não conseguiu parsear
            avisos.append(f"radon cc não leu {Path(arquivo).name}: {entradas.get('error')}")
            continue
        complexidades += [b["complexity"] for b in _funcoes(entradas)]
    if not complexidades:
        avisos.append("nenhuma função/método encontrado — cc_media fica vazia")
        return None
    return round(sum(complexidades) / len(complexidades), 4)


def metricas_brutas(alvo: Path, avisos: list[str]) -> dict[str, dict]:
    """Saída do `radon raw` por arquivo (usada para `loc` e para ponderar o `mi`)."""
    brutas = {}
    for arquivo, medidas in _radon("raw", alvo).items():
        if "error" in medidas:
            avisos.append(f"radon raw não leu {Path(arquivo).name}: {medidas['error']}")
            continue
        brutas[arquivo] = medidas
    return brutas


def indice_manutenibilidade(alvo: Path, brutas: dict[str, dict], avisos: list[str]) -> float | None:
    """Índice de manutenibilidade médio, ponderado pelo `sloc` de cada arquivo."""
    soma = peso_total = 0.0
    for arquivo, medidas in _radon("mi", alvo).items():
        if "error" in medidas:
            avisos.append(f"radon mi não leu {Path(arquivo).name}: {medidas['error']}")
            continue
        peso = max(brutas.get(arquivo, {}).get("sloc", 0), 1)
        soma += medidas["mi"] * peso
        peso_total += peso
    return round(soma / peso_total, 4) if peso_total else None


# ----------------------------------------------------------------------------- jscpd


def duplicacao_pct(alvo: Path, avisos: list[str], min_lines: int, min_tokens: int) -> float | None:
    """% de linhas duplicadas (`jscpd`). Devolve None — e avisa — se o jscpd não existir."""
    if shutil.which("jscpd") is None:
        avisos.append("jscpd não encontrado (npm install -g jscpd) — duplicacao_pct fica vazia")
        return None
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            ["jscpd", str(alvo), "--reporters", "json", "--output", tmp, "--silent",
             "--min-lines", str(min_lines), "--min-tokens", str(min_tokens)],
            capture_output=True, text=True, check=False,
        )
        relatorio = Path(tmp) / "jscpd-report.json"
        if not relatorio.exists():
            avisos.append(f"jscpd não gerou relatório: {proc.stderr.strip() or proc.stdout.strip()}")
            return None
        total = json.loads(relatorio.read_text(encoding="utf-8")).get("statistics", {}).get("total", {})
    if "percentage" not in total:
        avisos.append("jscpd não reportou percentual de duplicação")
        return None
    return round(float(total["percentage"]), 4)


# --------------------------------------------------------------------------- medição


def medir(kata_dir: Path, min_lines: int, min_tokens: int) -> tuple[dict, list[str]]:
    """Roda todas as ferramentas sobre o código de solução e devolve (métricas, avisos)."""
    avisos: list[str] = []
    arquivos = arquivos_solucao(kata_dir)
    if not arquivos:
        return {}, [f"nenhum arquivo de solução .py em {kata_dir}"]

    # Copiar para um diretório temporário: radon e jscpd passam a ver o mesmo conjunto
    # de arquivos, sem depender de padrões de exclusão diferentes em cada ferramenta.
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "solucao"
        for arquivo in arquivos:
            destino = base / arquivo.relative_to(kata_dir)
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(arquivo, destino)

        brutas = metricas_brutas(base, avisos)
        metricas = {
            "cc_media": complexidade_media(base, avisos),
            "loc": sum(m["sloc"] for m in brutas.values()) if brutas else None,
            "mi": indice_manutenibilidade(base, brutas, avisos),
            "duplicacao_pct": duplicacao_pct(base, avisos, min_lines, min_tokens),
        }
    return metricas, avisos


# ------------------------------------------------------------------------------- csv


def atualizar_csv(saida: Path, colunas: list[str], chave: dict, metricas: dict) -> str:
    """Grava as métricas na linha do trial. Devolve "atualizada" ou "criada".

    A linha é casada por `integrante` + `kata` + `tratamento` — a mesma chave usada pelo
    script de cronometragem (#40). Se ela ainda não existe, a linha é criada com as
    colunas de tempo vazias, para que a medição não se perca; o chamador avisa.
    """
    saida.parent.mkdir(parents=True, exist_ok=True)
    linhas: list[dict] = []
    if saida.exists():
        with saida.open(newline="", encoding="utf-8") as fh:
            linhas = list(csv.DictReader(fh))

    valores = {c: ("" if metricas.get(c) is None else metricas[c]) for c in COLUNAS_METRICAS}
    alvos = [l for l in linhas if all(l.get(k) == v for k, v in chave.items())]
    for linha in alvos:
        linha.update(valores)
    if not alvos:
        linhas.append({**{c: "" for c in colunas}, **chave, **valores})

    with saida.open("w", newline="", encoding="utf-8") as fh:
        # lineterminator="\n": Lab02 padroniza CSV em LF (Unix), igual ao template do #39.
        escritor = csv.DictWriter(fh, fieldnames=colunas, extrasaction="ignore", lineterminator="\n")
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow({c: linha.get(c, "") for c in colunas})
    return "atualizada" if alvos else "criada"


# ------------------------------------------------------------------------------ lote


def descobrir_trials(base: Path) -> list[tuple[str, str, str, Path]]:
    """Varre `<base>/<integrante>/<kata>/<tratamento>/` e devolve os trials encontrados."""
    trials = []
    for dir_integrante in sorted(p for p in base.iterdir() if p.is_dir()):
        for dir_kata in sorted(p for p in dir_integrante.iterdir() if p.is_dir()):
            for tratamento in TRATAMENTOS:
                dir_trial = dir_kata / tratamento
                if dir_trial.is_dir():
                    trials.append((dir_integrante.name, dir_kata.name, tratamento, dir_trial))
    return trials


# ------------------------------------------------------------------------------ main


def processar(integrante: str, kata: str, tratamento: str, kata_dir: Path,
              saida: Path, colunas: list[str], min_lines: int, min_tokens: int) -> bool:
    """Mede um trial e grava no CSV. Devolve False se não houve o que medir."""
    rotulo = f"{integrante} · {kata} · {tratamento}"
    metricas, avisos = medir(kata_dir, min_lines, min_tokens)
    if not metricas:
        for aviso in avisos:
            print(f"  AVISO [{rotulo}]: {aviso}")
        return False

    chave = {"integrante": integrante, "kata": kata, "tratamento": tratamento}
    estado = atualizar_csv(saida, colunas, chave, metricas)
    if estado == "criada":
        avisos.append("nenhuma linha de cronometragem (#40) para este trial — linha criada "
                      "com as colunas de tempo vazias")

    resumo = ", ".join(
        f"{c}={'—' if metricas[c] is None else metricas[c]}" for c in COLUNAS_METRICAS
    )
    print(f"  {rotulo}: {resumo} (linha {estado})")
    for aviso in avisos:
        print(f"  AVISO [{rotulo}]: {aviso}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Métricas estáticas de um trial (RQ3, Issue #41).")
    parser.add_argument("--integrante", help="login do GitHub de quem executou o trial")
    parser.add_argument("--kata", help="id do kata (ex.: k1)")
    parser.add_argument("--tratamento", choices=list(TRATAMENTOS), help="uso ou não do assistente de IA")
    parser.add_argument("--kata-dir", type=Path, help="diretório com o código final do trial")
    parser.add_argument("--lote", action="store_true",
                        help="mede todos os trials de --trials-dir em vez de um só")
    parser.add_argument("--trials-dir", type=Path, default=TRIALS_PADRAO,
                        help=f"raiz dos trials arquivados (padrão {TRIALS_PADRAO.relative_to(RAIZ)})")
    parser.add_argument("--min-lines", type=int, default=JSCPD_MIN_LINES,
                        help=f"jscpd: mínimo de linhas de um clone (padrão {JSCPD_MIN_LINES})")
    parser.add_argument("--min-tokens", type=int, default=JSCPD_MIN_TOKENS,
                        help=f"jscpd: mínimo de tokens de um clone (padrão {JSCPD_MIN_TOKENS})")
    parser.add_argument("--out", type=Path, default=SAIDA_PADRAO, help="CSV de coleta")
    args = parser.parse_args(argv)

    colunas = carregar_colunas()

    if args.lote:
        if not args.trials_dir.is_dir():
            parser.error(f"--trials-dir não é um diretório: {args.trials_dir}")
        trials = descobrir_trials(args.trials_dir)
        if not trials:
            parser.error(f"nenhum trial em {args.trials_dir} — o layout esperado é "
                         "<integrante>/<kata>/<com_ia|sem_ia>/")
        print(f"Medindo {len(trials)} trial(s) em {args.trials_dir}...")
        medidos = sum(processar(i, k, t, d, args.out, colunas, args.min_lines, args.min_tokens)
                      for i, k, t, d in trials)
        print(f"{medidos}/{len(trials)} trial(s) medidos. CSV: {args.out}")
        return 0 if medidos == len(trials) else 1

    faltando = [f"--{n.replace('_', '-')}" for n in ("integrante", "kata", "tratamento", "kata_dir")
                if getattr(args, n) is None]
    if faltando:
        parser.error(f"sem --lote, estes argumentos são obrigatórios: {', '.join(faltando)}")
    if not args.kata_dir.is_dir():
        parser.error(f"--kata-dir não é um diretório: {args.kata_dir}")

    print(f"Medindo métricas estáticas de {args.kata_dir}...")
    ok = processar(args.integrante, args.kata, args.tratamento, args.kata_dir,
                   args.out, colunas, args.min_lines, args.min_tokens)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

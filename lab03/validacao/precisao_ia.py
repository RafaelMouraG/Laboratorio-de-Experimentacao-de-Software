"""Precisão da detecção de agentes (#120), a partir das planilhas conferidas.

`python -m lab03.validacao.precisao_ia`, da raiz do repositório, depois que os três preencheram
`com_agente` em `rotulos/<login>_ia.csv`.

O consenso de cada commit é o rótulo da maioria (2 de 3). Sem maioria (um `sim`, um `nao` e um
`incerto`), o commit fica `sem_consenso`. A precisão é `sim / (sim + nao)` no consenso: `incerto` e
`sem_consenso` ficam de fora da conta e são contados à parte.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence

from lab03.validacao.concordancia import ErroRotulagem
from lab03.validacao.sortear import AVALIADORES

PASTA = Path("lab03/validacao")
ROTULOS = frozenset(("sim", "nao", "incerto"))
SEM_CONSENSO = "sem_consenso"


def ler_planilha(caminho: Path) -> dict[str, str]:
    """sha -> rótulo. Recusa rótulo vazio ou fora de `ROTULOS`."""
    with caminho.open(encoding="utf-8") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    rotulos = {}
    for linha in linhas:
        valor = (linha.get("com_agente") or "").strip()
        if valor not in ROTULOS:
            raise ErroRotulagem(f"{caminho.name}: {linha['sha'][:7]} com com_agente {valor!r}")
        rotulos[linha["sha"]] = valor
    return rotulos


def consenso(rotulos: Sequence[str]) -> str:
    valor, votos = Counter(rotulos).most_common(1)[0]
    return valor if votos * 2 > len(rotulos) else SEM_CONSENSO


def precisao(por_avaliador: Mapping[str, Mapping[str, str]]) -> dict:
    """Consenso de cada commit e a precisão. Todos os avaliadores precisam ter os mesmos commits."""
    conjuntos = {login: set(r) for login, r in por_avaliador.items()}
    primeiro = next(iter(conjuntos.values()))
    if any(c != primeiro for c in conjuntos.values()):
        raise ErroRotulagem("as planilhas não têm os mesmos commits")
    decisoes = {sha: consenso([r[sha] for r in por_avaliador.values()]) for sha in sorted(primeiro)}
    contagem = Counter(decisoes.values())
    avaliados = contagem["sim"] + contagem["nao"]
    return {
        "decisoes": decisoes,
        "sim": contagem["sim"],
        "nao": contagem["nao"],
        "incerto": contagem["incerto"],
        "sem_consenso": contagem[SEM_CONSENSO],
        "precisao": contagem["sim"] / avaliados if avaliados else None,
    }


def main() -> int:
    try:
        por_avaliador = {login: ler_planilha(PASTA / "rotulos" / f"{login}_ia.csv") for login in AVALIADORES}
        resultado = precisao(por_avaliador)
    except (ErroRotulagem, FileNotFoundError) as erro:
        print(erro, file=sys.stderr)
        return 1
    with (PASTA / "consenso_ia.csv").open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(["sha", "consenso"])
        escritor.writerows(resultado["decisoes"].items())
    p = resultado["precisao"]
    print(f"sim {resultado['sim']}, nao {resultado['nao']}, incerto {resultado['incerto']}, "
          f"sem consenso {resultado['sem_consenso']}; precisão {'-' if p is None else f'{p:.3f}'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

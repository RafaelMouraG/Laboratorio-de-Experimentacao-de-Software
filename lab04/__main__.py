"""`python -m lab04`, da raiz do repositório: roda o lab inteiro e gera o dashboard."""

from __future__ import annotations

from lab04.dashboard.pagina import gerar
from lab04.simulacao import motor, q1, q2, q3


def main() -> int:
    for questao in (q1, q2, q3):
        motor.gravar(questao.rodar())
    print(f"simulações em {motor.SAIDA}")
    print(f"dashboard em {gerar()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

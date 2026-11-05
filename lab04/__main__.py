"""`python -m lab04`, da raiz do repositório: roda o lab inteiro e gera o dashboard."""

from __future__ import annotations

from lab04.dashboard.pagina import gerar
from lab04.simulacao import motor, q1, q2


def main() -> int:
    motor.gravar(q1.rodar())
    motor.gravar(q2.rodar())
    print(f"simulações em {motor.SAIDA}")
    print(f"dashboard em {gerar()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""`python -m lab04`, da raiz do repositório: gera o dashboard dos dados versionados."""

from __future__ import annotations

from lab04.dashboard.pagina import gerar


def main() -> int:
    print(f"dashboard em {gerar()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

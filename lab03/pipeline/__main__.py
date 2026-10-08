"""`python -m lab03.pipeline --config lab03/config.yaml [--limite N]`, a partir da raiz do repositório."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

import yaml

from lab03.pipeline.api import ErroAPI, GitHubAPI
from lab03.pipeline.coleta import executar

PASTA_SAIDA = "lab03/data"

log = logging.getLogger("lab03.pipeline")


def _data_config(config: dict, campo: str) -> date:
    valor = (config.get("janela") or {}).get(campo)
    if not valor:
        raise SystemExit(f"janela.{campo} não definida no config (AAAA-MM-DD).")
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor))


def carregar_config(caminho: str | Path) -> dict:
    with open(caminho, encoding="utf-8") as arquivo:
        config = yaml.safe_load(arquivo) or {}
    config["inicio"] = _data_config(config, "inicio")
    config["fim"] = _data_config(config, "fim")
    if config["inicio"] > config["fim"]:
        raise SystemExit("janela.inicio depois de janela.fim.")
    return config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lab03.pipeline", description=__doc__)
    parser.add_argument("--config", default="lab03/config.yaml")
    parser.add_argument("--limite", type=int, help="tamanho da amostra (padrão: limite_repos do config)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    config = carregar_config(args.config)
    limite = args.limite or config.get("limite_repos", 100)
    pasta_cache = config.get("pasta_cache", "lab03/data/cache")
    pasta_saida = config.get("pasta_saida", PASTA_SAIDA)

    api = GitHubAPI.do_ambiente(pasta_cache)
    try:
        api.restante = api.cota()["core"]["remaining"]
    except Exception as erro:  # só serve para a linha de progresso
        log.warning("não deu para ler a cota inicial: %s", erro)

    try:
        executar(
            api,
            config["faixas_estrelas"],
            config["inicio"],
            config["fim"],
            limite,
            pasta_cache,
            pasta_saida,
            coletar_tags=config.get("coletar_tags", False),
        )
    except KeyboardInterrupt:
        log.warning("interrompido; rode o mesmo comando para continuar de onde parou")
        return 130
    except ErroAPI as erro:
        if erro.status == 401:
            raise SystemExit("GITHUB_TOKEN recusado pelo GitHub (401): token inválido ou expirado.")
        raise
    log.info("CSVs em %s (%d chamadas de rede nesta execução)", pasta_saida, api.chamadas_rede)
    return 0


if __name__ == "__main__":
    sys.exit(main())

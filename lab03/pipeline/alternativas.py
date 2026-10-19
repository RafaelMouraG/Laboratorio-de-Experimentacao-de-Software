"""`python -m lab03.pipeline.alternativas --config lab03/config.yaml [--limite N]`, da raiz do repositório.

Entregas nas unidades de deploy alternativas da RQ 07, para os repositórios que já estão no
`repos.csv`: release + pré-release (C2) e tag (C3). Fica fora do pipeline principal para não mexer
nos marcadores `_completo` da coleta pesada. Cada repo terminado ganha o marcador `_alternativas`
na pasta dele no cache, então parar e rodar de novo continua de onde parou.
"""

from __future__ import annotations

import argparse
import csv
import logging
from datetime import date
from pathlib import Path

from lab03.pipeline import releases
from lab03.pipeline.__main__ import PASTA_SAIDA, carregar_config
from lab03.pipeline.api import ErroAPI, GitHubAPI, RecursoAusente
from lab03.pipeline.coleta import _escrever_csv, gravar_marcador, ler_marcador

MARCADOR = "_alternativas"
CAMPOS_RELEASES_PRE = (
    "repo", "tag_name", "published_at", "prerelease", "html_url", "commits",
    "sem_anterior", "ignorada_compare_404",
)
CAMPOS_TAGS = ("repo", "tag_name", "sha", "published_at", "commits", "sem_anterior", "ignorada_compare_404")

log = logging.getLogger("lab03.pipeline.alternativas")


def repos_da_amostra(pasta_saida: str | Path) -> list[str]:
    with open(Path(pasta_saida) / "repos.csv", encoding="utf-8") as arquivo:
        return [linha["repo"] for linha in csv.DictReader(arquivo)]


def coletar_repo(api: GitHubAPI, repo: str, inicio: date, fim: date) -> dict:
    """As duas unidades de um repo. Repo que sumiu ou deu erro sai com `erro` e listas vazias."""
    try:
        com_pre = releases.coletar(api, repo, inicio, fim, com_pre=True)["releases"]
        tags = releases.entregas_por_tag(api, repo, inicio, fim)
    except (RecursoAusente, ErroAPI) as erro:
        log.warning("%s: %s", repo, erro)
        return {"repo": repo, "erro": str(erro), "releases_pre": [], "tags": []}
    return {"repo": repo, "erro": None, "releases_pre": com_pre, "tags": tags}


def salvar_csvs(pasta_saida: str | Path, resultados: list[dict]) -> None:
    pasta = Path(pasta_saida)
    _escrever_csv(
        pasta / "releases_pre.csv",
        CAMPOS_RELEASES_PRE,
        ({**rel, "repo": r["repo"], "commits": len(rel["commits"])} for r in resultados for rel in r["releases_pre"]),
    )
    _escrever_csv(
        pasta / "tags.csv",
        CAMPOS_TAGS,
        ({**tag, "repo": r["repo"], "commits": len(tag["commits"])} for r in resultados for tag in r["tags"]),
    )


def executar(
    api: GitHubAPI, repos: list[str], inicio: date, fim: date, pasta_cache: str | Path, pasta_saida: str | Path
) -> list[dict]:
    assinatura = {"inicio": str(inicio), "fim": str(fim), "campos_release": list(releases.CAMPOS_RELEASE)}
    resultados = []
    for i, repo in enumerate(repos, start=1):
        resultado = ler_marcador(pasta_cache, repo, assinatura, MARCADOR)
        if resultado is None:
            antes = api.chamadas_rede
            resultado = coletar_repo(api, repo, inicio, fim)
            if resultado["erro"] is None:
                gravar_marcador(pasta_cache, repo, assinatura, resultado, MARCADOR)
            log.info("%d/%d %s: %d releases+pré, %d tags | %d chamadas | cota %s", i, len(repos), repo,
                     len(resultado["releases_pre"]), len(resultado["tags"]), api.chamadas_rede - antes,
                     "?" if api.restante is None else api.restante)
        resultados.append(resultado)
    salvar_csvs(pasta_saida, resultados)
    return resultados


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lab03.pipeline.alternativas", description=__doc__)
    parser.add_argument("--config", default="lab03/config.yaml")
    parser.add_argument("--limite", type=int, help="só os N primeiros repositórios do repos.csv")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    config = carregar_config(args.config)
    pasta_cache = config.get("pasta_cache", "lab03/data/cache")
    pasta_saida = config.get("pasta_saida", PASTA_SAIDA)
    repos = repos_da_amostra(pasta_saida)[: args.limite]

    api = GitHubAPI.do_ambiente(pasta_cache)
    try:
        executar(api, repos, config["inicio"], config["fim"], pasta_cache, pasta_saida)
    except KeyboardInterrupt:
        log.warning("interrompido; rode o mesmo comando para continuar de onde parou")
        return 130
    log.info("releases_pre.csv e tags.csv em %s (%d chamadas de rede nesta execução)",
             pasta_saida, api.chamadas_rede)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

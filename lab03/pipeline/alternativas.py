"""`python -m lab03.pipeline.alternativas --config lab03/config.yaml [--limite N]`, da raiz do repositório.

Entregas nas unidades de deploy alternativas da RQ 07, para os repositórios que já estão no
`repos.csv`: release + pré-release (C2) e tag (C3). Fica fora do pipeline principal para não mexer
nos marcadores `_completo` da coleta pesada. Cada unidade terminada num repo ganha um marcador na
pasta dele no cache (`_alternativas_pre` e `_alternativas_tag`), então parar e rodar de novo continua
de onde parou. Junto com as entregas sai o `metricas_c2.csv` ou o `metricas_c3.csv`, com a frequência,
os dois lead times e a CFR (b) de cada repo na unidade, que é o que a RQ 07 compara. Com `--unidade` dá para coletar uma só: a C3 custa bem mais cota que a C2. Com
`--tags-de-versao`, a C3 só considera tags com `X.Y` ou `X.Y.Z` no nome ou com release publicada de
mesmo nome, o que deixa de fora tags de CI como `ciflow/trunk/123` e `viable/strict/456` sem perder
releases com nome fora do padrão (`b6500` no llama.cpp, `r170` no three.js, `langchain==1.0.0`).
"""

from __future__ import annotations

import argparse
import csv
import logging
from datetime import date
from pathlib import Path
from typing import Callable

from lab03.metricas.classificacao import faixa_cfr, faixa_frequencia, faixa_lead_time
from lab03.metricas.corretiva import cfr_entrega, versao
from lab03.metricas.frequencia import releases_por_semana
from lab03.metricas.lead_time import lead_time_por_commit, lead_time_por_release
from lab03.pipeline import releases
from lab03.pipeline.__main__ import PASTA_SAIDA, carregar_config
from lab03.pipeline.api import ErroAPI, GitHubAPI, RecursoAusente
from lab03.pipeline.coleta import _escrever_csv, gravar_marcador, ler_marcador

UNIDADES = ("pre", "tag")
CAMPOS = {
    "pre": ("repo", "tag_name", "published_at", "prerelease", "html_url", "commits",
            "sem_anterior", "ignorada_compare_404"),
    "tag": ("repo", "tag_name", "sha", "published_at", "commits", "sem_anterior", "ignorada_compare_404"),
}
ARQUIVOS = {"pre": "releases_pre.csv", "tag": "tags.csv"}
ARQUIVOS_METRICAS = {"pre": "metricas_c2.csv", "tag": "metricas_c3.csv"}
CAMPOS_METRICAS = (
    "repo", "entregas", "entregas_por_semana", "faixa_frequencia",
    "lead_time_release_horas", "lead_time_release_avaliadas", "faixa_lead_time_release",
    "lead_time_commit_horas", "lead_time_commit_avaliadas", "faixa_lead_time_commit",
    "cfr_entrega", "cfr_entrega_avaliadas", "cfr_entrega_falharam", "faixa_cfr_entrega",
)

log = logging.getLogger("lab03.pipeline.alternativas")


def repos_da_amostra(pasta_saida: str | Path) -> list[str]:
    with open(Path(pasta_saida) / "repos.csv", encoding="utf-8") as arquivo:
        return [linha["repo"] for linha in csv.DictReader(arquivo)]


def filtro_de_versao(nomes_de_release: set[str]) -> Callable[[str], bool]:
    """Tag com versão pelo critério da heurística corretiva, ou com release publicada de mesmo nome."""
    return lambda nome: versao(nome) is not None or nome in nomes_de_release


def coletar_repo(
    api: GitHubAPI, repo: str, unidade: str, inicio: date, fim: date, tags_de_versao: bool = False
) -> dict:
    """Entregas de um repo numa unidade. Repo que sumiu ou deu erro sai com `erro` e lista vazia."""
    try:
        if unidade == "pre":
            entregas = releases.coletar(api, repo, inicio, fim, com_pre=True)["releases"]
        else:
            filtro = None
            if tags_de_versao:  # a lista de releases já está no cache da coleta principal
                filtro = filtro_de_versao({r["tag_name"] for r in releases.listar_releases(api, repo)})
            entregas = releases.entregas_por_tag(api, repo, inicio, fim, filtro)
    except (RecursoAusente, ErroAPI) as erro:
        log.warning("%s: %s", repo, erro)
        return {"repo": repo, "erro": str(erro), "entregas": []}
    return {"repo": repo, "erro": None, "entregas": entregas}


def metricas_da_unidade(resultado: dict, inicio: date, fim: date) -> dict:
    """Frequência, lead time (a) e (b) e CFR (b) das entregas de um repo, com as funções de
    `lab03/metricas`. Tag não tem notas, e a v4 da heurística sem notas vira a v3 (só o patch).
    Repo com erro na coleta sai com tudo vazio."""
    if resultado["erro"] is not None:
        return {"repo": resultado["repo"]}
    entregas = resultado["entregas"]
    frequencia = releases_por_semana((e["published_at"] for e in entregas), inicio, fim)
    por_release, por_commit = lead_time_por_release(entregas), lead_time_por_commit(entregas)
    falhas = cfr_entrega(entregas, fim)
    return {
        "repo": resultado["repo"],
        "entregas": len(entregas),
        "entregas_por_semana": frequencia,
        "faixa_frequencia": faixa_frequencia(frequencia),
        "lead_time_release_horas": por_release.mediana_horas,
        "lead_time_release_avaliadas": por_release.valores,
        "faixa_lead_time_release": faixa_lead_time(por_release.mediana_horas),
        "lead_time_commit_horas": por_commit.mediana_horas,
        "lead_time_commit_avaliadas": por_commit.valores,
        "faixa_lead_time_commit": faixa_lead_time(por_commit.mediana_horas),
        "cfr_entrega": falhas.taxa,
        "cfr_entrega_avaliadas": falhas.avaliadas,
        "cfr_entrega_falharam": falhas.falharam,
        "faixa_cfr_entrega": faixa_cfr(falhas.taxa),
    }


def salvar_csv(pasta_saida: str | Path, unidade: str, resultados: list[dict]) -> None:
    _escrever_csv(
        Path(pasta_saida) / ARQUIVOS[unidade],
        CAMPOS[unidade],
        ({**e, "repo": r["repo"], "commits": len(e["commits"])} for r in resultados for e in r["entregas"]),
    )


def executar(
    api: GitHubAPI,
    repos: list[str],
    inicio: date,
    fim: date,
    pasta_cache: str | Path,
    pasta_saida: str | Path,
    unidades: tuple[str, ...] = UNIDADES,
    tags_de_versao: bool = False,
) -> dict[str, list[dict]]:
    base = {"inicio": str(inicio), "fim": str(fim), "campos_release": list(releases.CAMPOS_RELEASE)}
    todos = {}
    for unidade in unidades:
        marcador = f"_alternativas_{unidade}"
        assinatura = {**base, "tags_de_versao": "versao_ou_release" if tags_de_versao else False} if unidade == "tag" else base
        resultados = []
        for i, repo in enumerate(repos, start=1):
            resultado = ler_marcador(pasta_cache, repo, assinatura, marcador)
            if resultado is None:
                antes = api.chamadas_rede
                resultado = coletar_repo(api, repo, unidade, inicio, fim, tags_de_versao)
                if resultado["erro"] is None:
                    gravar_marcador(pasta_cache, repo, assinatura, resultado, marcador)
                log.info("%s %d/%d %s: %d entregas | %d chamadas | cota %s", unidade, i, len(repos), repo,
                         len(resultado["entregas"]), api.chamadas_rede - antes,
                         "?" if api.restante is None else api.restante)
            resultados.append(resultado)
        salvar_csv(pasta_saida, unidade, resultados)
        _escrever_csv(Path(pasta_saida) / ARQUIVOS_METRICAS[unidade], CAMPOS_METRICAS,
                      (metricas_da_unidade(r, inicio, fim) for r in resultados))
        todos[unidade] = resultados
    return todos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lab03.pipeline.alternativas", description=__doc__)
    parser.add_argument("--config", default="lab03/config.yaml")
    parser.add_argument("--limite", type=int, help="só os N primeiros repositórios do repos.csv")
    parser.add_argument("--unidade", choices=UNIDADES, help="só release + pré-release (pre) ou só tag (tag)")
    parser.add_argument("--tags-de-versao", action="store_true",
                        help="na C3, só tags com X.Y ou X.Y.Z no nome ou com release (tira tags de CI)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    config = carregar_config(args.config)
    pasta_cache = config.get("pasta_cache", "lab03/data/cache")
    pasta_saida = config.get("pasta_saida", PASTA_SAIDA)
    repos = repos_da_amostra(pasta_saida)[: args.limite]

    api = GitHubAPI.do_ambiente(pasta_cache)
    try:
        unidades = (args.unidade,) if args.unidade else UNIDADES
        executar(api, repos, config["inicio"], config["fim"], pasta_cache, pasta_saida, unidades,
                 args.tags_de_versao)
    except KeyboardInterrupt:
        log.warning("interrompido; rode o mesmo comando para continuar de onde parou")
        return 130
    log.info("CSVs em %s (%d chamadas de rede nesta execução)", pasta_saida, api.chamadas_rede)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

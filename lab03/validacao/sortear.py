"""Sorteio da amostra-ouro e as planilhas de rotulagem (seção 6 do enunciado).

`python -m lab03.validacao.sortear --config lab03/config.yaml`, da raiz do repositório.

1. 60 repositórios de `repos.csv`, com `sample(n=60, random_state=42)`.
2. Em cada um, 5 releases da janela, também com semente fixa, só entre as que têm release anterior
   e compare válido: sem isso não existe lista de commits para quem for rotular.
3. Para cada avaliador, uma planilha de repositórios e uma de releases, com os rótulos vazios.
   Planilha que já existe não é sobrescrita, para rodar de novo não apagar o que alguém rotulou.
4. `heuristica_entrada.jsonl.gz`: o que a heurística de release corretiva (#96) recebe para essas
   mesmas releases. Fica fora das planilhas, para ninguém rotular olhando o que ela decidiu. Vai
   comprimido porque release cuja anterior é de outra linha de versão (`v8.19.4` → `v9.1.5`) traz
   milhares de commits no compare. Leitura: `pd.read_json(caminho, lines=True)`.

Tudo que vem da API sai do cache da coleta; numa máquina sem cache são umas 600 chamadas.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import logging
import sys
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import quote

import pandas as pd

from lab03.pipeline import releases
from lab03.pipeline.__main__ import carregar_config
from lab03.pipeline.api import GitHubAPI, RecursoAusente

SEMENTE = 42
N_REPOS = 60
N_RELEASES = 5
AVALIADORES = ("mateusdsoc", "RafaelMouraG", "Athoosz")
PASTA = Path("lab03/validacao")
ENTRADA_HEURISTICA = "heuristica_entrada.jsonl.gz"

CAMPOS_ROTULO_REPOS = ("repo", "url", "tipo_projeto", "entregas_reais", "observacao")
CAMPOS_ROTULO_RELEASES = ("repo", "tag_name", "url_release", "url_compare", "corretiva", "observacao")
CAMPOS_AMOSTRA_REPOS = ("repo", "url", "estrelas", "linguagem")
CAMPOS_AMOSTRA_RELEASES = ("repo", "tag_name", "published_at", "tag_anterior", "url_release",
                           "url_compare", "commits")

log = logging.getLogger(__name__)


def sortear_repos(repos: pd.DataFrame, n: int = N_REPOS, semente: int = SEMENTE) -> pd.DataFrame:
    """`n` linhas de `repos.csv`, no sorteio do enunciado. A ordem final é alfabética, só para a
    planilha ficar fácil de navegar; quem entra é decidido pelo `sample`."""
    return repos.sample(n=min(n, len(repos)), random_state=semente).sort_values("repo")


def url_compare(repo: str, anterior: str, tag: str) -> str:
    return f"https://github.com/{repo}/compare/{quote(anterior, safe='')}...{quote(tag, safe='')}"


def sortear_releases(
    api: GitHubAPI, repo: str, inicio, fim, n: int = N_RELEASES, semente: int = SEMENTE
) -> list[dict]:
    """Embaralha as releases da janela que têm anterior e fica com as `n` primeiras cujo compare
    existe. Cada uma sai com a anterior, as notas e os commits, que é o que a heurística lê."""
    todas = releases.listar_releases(api, repo)
    # mesma consulta do listar_releases, então sai do cache
    notas = {r["tag_name"]: r.get("body") or "" for r in api.paginar(f"/repos/{repo}/releases")}
    candidatas = []
    for release in releases.releases_na_janela(todas, inicio, fim):
        anterior = releases.release_anterior(todas, release)
        if anterior is not None:
            candidatas.append({**release, "anterior": anterior})
    if not candidatas:
        return []

    embaralhadas = pd.DataFrame(candidatas).sample(frac=1, random_state=semente).to_dict("records")
    escolhidas = []
    for release in embaralhadas:
        anterior = release["anterior"]
        try:
            commits = releases.commits_da_release(api, repo, anterior["tag_name"], release["tag_name"])
        except RecursoAusente:
            log.info("%s: compare %s...%s não existe, sorteando outra", repo, anterior["tag_name"],
                     release["tag_name"])
            continue
        escolhidas.append({
            "repo": repo,
            "tag_name": release["tag_name"],
            "published_at": release["published_at"],
            "url_release": release["html_url"],
            "url_compare": url_compare(repo, anterior["tag_name"], release["tag_name"]),
            "notas": notas.get(release["tag_name"], ""),
            "anterior": {"tag_name": anterior["tag_name"], "published_at": anterior["published_at"]},
            "commits": commits,
        })
        if len(escolhidas) == n:
            break
    if len(escolhidas) < n:
        log.warning("%s: só %d releases com compare válido para sortear", repo, len(escolhidas))
    return sorted(escolhidas, key=lambda r: r["published_at"])


def _escrever_csv(caminho: Path, campos: Iterable[str], linhas: Iterable[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(campos), extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(linhas)


def gravar(pasta: Path, amostra: pd.DataFrame, sorteadas: list[dict],
           avaliadores: Iterable[str] = AVALIADORES) -> list[Path]:
    """Grava a amostra, a entrada da heurística e as planilhas. Devolve as planilhas mantidas."""
    amostra = amostra.fillna({"linguagem": ""})
    linhas_repos = [{"repo": r, "url": f"https://github.com/{r}", "estrelas": e, "linguagem": l}
                    for r, e, l in zip(amostra["repo"], amostra["estrelas"], amostra["linguagem"])]
    linhas_releases = [{**r, "tag_anterior": r["anterior"]["tag_name"], "commits": len(r["commits"])}
                       for r in sorteadas]
    _escrever_csv(pasta / "amostra_ouro_repos.csv", CAMPOS_AMOSTRA_REPOS, linhas_repos)
    _escrever_csv(pasta / "amostra_ouro_releases.csv", CAMPOS_AMOSTRA_RELEASES, linhas_releases)
    # mtime=0: o .gz sai igual byte a byte quando o sorteio é o mesmo
    with gzip.GzipFile(pasta / ENTRADA_HEURISTICA, "wb", mtime=0) as bruto, \
            io.TextIOWrapper(bruto, encoding="utf-8") as arquivo:
        for release in sorteadas:
            campos = ("repo", "tag_name", "published_at", "notas", "anterior", "commits")
            arquivo.write(json.dumps({c: release[c] for c in campos}, ensure_ascii=False) + "\n")

    mantidas = []
    for login in avaliadores:
        for sufixo, campos, linhas in (("repos", CAMPOS_ROTULO_REPOS, linhas_repos),
                                       ("releases", CAMPOS_ROTULO_RELEASES, linhas_releases)):
            planilha = pasta / "rotulos" / f"{login}_{sufixo}.csv"
            if planilha.exists():
                mantidas.append(planilha)
                continue
            _escrever_csv(planilha, campos, linhas)
    return mantidas


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lab03.validacao.sortear", description=__doc__.split("\n")[0])
    parser.add_argument("--config", default="lab03/config.yaml")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    config = carregar_config(args.config)
    pasta_saida = Path(config.get("pasta_saida", "lab03/data"))
    api = GitHubAPI.do_ambiente(config.get("pasta_cache", "lab03/data/cache"))

    amostra = sortear_repos(pd.read_csv(pasta_saida / "repos.csv"))
    sorteadas = []
    for repo in amostra["repo"]:
        sorteadas.extend(sortear_releases(api, repo, config["inicio"], config["fim"]))
    mantidas = gravar(PASTA, amostra, sorteadas)

    log.info("%d repositórios e %d releases em %s (%d chamadas de rede)",
             len(amostra), len(sorteadas), PASTA, api.chamadas_rede)
    for planilha in mantidas:
        log.warning("%s já existia e foi mantida; apague para gerar de novo", planilha)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""`python -m lab04.data.coleta_prs`, da raiz do repositório: grava `lab04/data/prs.csv`.

Sorteia PRs mergeados de um repositório, com e sem review do CodeRabbit, no mesmo período. A coleta
fica fora do comando único: o CSV versionado é o que a análise usa, e assim o resultado não muda
conforme o que o GitHub devolve no dia.
"""

from __future__ import annotations

import csv
import os
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import requests
from dotenv import load_dotenv

REPOSITORIO = "langflow-ai/langflow"
PERIODO = "2026-08-01..2026-10-31"
BOT_REVISOR = "coderabbitai[bot]"
POR_GRUPO = 30
MINUTOS_MINIMOS = 10
SEMENTE = 42
PAUSA_BUSCA = 10  # segundos; a busca do GitHub barra chamadas seguidas
DESTINO = Path(__file__).with_name("prs.csv")
CAMPOS = ("repo", "pr", "url", "autor", "grupo", "criado_em", "mergeado_em", "horas_ate_merge")
API = "https://api.github.com"


def _data(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def horas_ate_merge(criado_em: str, mergeado_em: str) -> float:
    return round((_data(mergeado_em) - _data(criado_em)).total_seconds() / 3600, 4)


def aberto_por_bot(pr: dict) -> bool:
    autor = pr["user"]
    return autor["type"] == "Bot" or autor["login"].endswith("[bot]")


def elegivel(pr: dict) -> bool:
    """Tira PR de bot, sincronização de branch ("Merge release-1.12.6 into main") e merge rápido demais
    para o CodeRabbit ter revisado: nesse caso, estar sem o bot não diz nada sobre o bot."""
    if aberto_por_bot(pr) or pr["title"].startswith("Merge "):
        return False
    return horas_ate_merge(pr["created_at"], pr["pull_request"]["merged_at"]) * 60 >= MINUTOS_MINIMOS


def entra_no_grupo(grupo: str, reviews: list[dict], mergeado_em: str) -> bool:
    """Com bot: o CodeRabbit revisou antes do merge. Sem bot: nenhum bot revisou o PR."""
    if grupo == "sem_bot":
        return not any(r["user"] and r["user"]["type"] == "Bot" for r in reviews)
    return any(r["user"] and r["user"]["login"] == BOT_REVISOR and r.get("submitted_at")
               and _data(r["submitted_at"]) < _data(mergeado_em) for r in reviews)


def buscar(sessao: requests.Session, filtro: str) -> list[dict]:
    consulta = f"repo:{REPOSITORIO} is:pr is:merged merged:{PERIODO} {filtro}"
    achados, pagina = [], 1
    while True:
        time.sleep(PAUSA_BUSCA)
        resposta = sessao.get(f"{API}/search/issues", params={"q": consulta, "per_page": 100, "page": pagina})
        if resposta.status_code == 403:  # limite secundário: espera e repete a mesma página
            time.sleep(int(resposta.headers.get("Retry-After", 60)))
            continue
        resposta.raise_for_status()
        itens = resposta.json()["items"]
        achados += itens
        if len(itens) < 100:
            # a ordem da busca muda entre chamadas; o sorteio precisa partir sempre da mesma lista
            return sorted(achados, key=lambda pr: pr["number"])
        pagina += 1


def sortear(sessao: requests.Session, prs: list[dict], grupo: str, rng: np.random.Generator) -> list[dict]:
    """Percorre os PRs em ordem sorteada até completar o grupo."""
    linhas = []
    for indice in rng.permutation(len(prs)):
        pr = prs[int(indice)]
        if not elegivel(pr):
            continue
        mergeado_em = pr["pull_request"]["merged_at"]
        resposta = sessao.get(f"{API}/repos/{REPOSITORIO}/pulls/{pr['number']}/reviews", params={"per_page": 100})
        resposta.raise_for_status()
        if entra_no_grupo(grupo, resposta.json(), mergeado_em):
            linhas.append({
                "repo": REPOSITORIO, "pr": pr["number"], "url": pr["html_url"], "autor": pr["user"]["login"],
                "grupo": grupo, "criado_em": pr["created_at"], "mergeado_em": mergeado_em,
                "horas_ate_merge": horas_ate_merge(pr["created_at"], mergeado_em),
            })
        if len(linhas) == POR_GRUPO:
            break
    return linhas


def main() -> int:
    load_dotenv()
    sessao = requests.Session()
    sessao.headers.update({"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                           "Accept": "application/vnd.github+json"})
    rng = np.random.default_rng(SEMENTE)
    linhas = []
    for grupo, filtro in (("com_bot", f"reviewed-by:{BOT_REVISOR}"), ("sem_bot", f"-reviewed-by:{BOT_REVISOR}")):
        prs = buscar(sessao, filtro)
        sorteados = sortear(sessao, prs, grupo, rng)
        print(f"{grupo}: {len(prs)} PRs no período, {len(sorteados)} sorteados")
        linhas += sorteados
    with open(DESTINO, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS)
        escritor.writeheader()
        escritor.writerows(linhas)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

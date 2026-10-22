"""Coleta dos rastros de adoção de agentes de IA (RQ 09, #117).

Roda depois da coleta principal, sobre os repositórios do `repos.csv`, e só acrescenta dados:
grava o `commits_ia.csv` e as colunas `agentes.CAMPOS_ADOCAO` no `repos.csv`, sem mexer nas outras.
Por repositório:

1. commits do default branch na janela, mês a mês, com as linhas da mensagem que a detecção usa
   (o compare da coleta principal guarda só a primeira, e o `Co-authored-by` fica no fim);
2. árvore do último commit da janela, atrás dos arquivos de agente, e o `.gitignore` dele;
3. PRs de agente pela busca de issues: um filtro por prefixo de branch, label e conta bot.

Interromper não joga nada fora. Cada página fica no cache da `GitHubAPI`, cada repositório
terminado ganha o marcador `_adocao` na pasta dele, e os CSVs são gravados com quem já terminou
mesmo quando a execução para no meio (Ctrl+C ou erro). Rodar de novo pula os marcados e retoma o
repo interrompido a partir das páginas em cache. A assinatura do marcador leva um hash de
`metricas/agentes.py` e deste arquivo: mudar uma regra refaz o resultado, mas só lendo o cache.
`--parcial` grava os CSVs só com os marcados, sem chamar a API.

Depois de rodar a coleta principal de novo, o `repos.csv` volta sem as colunas de adoção; basta
rodar `--adocao` outra vez, que sai inteiro do cache.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import logging
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote

from lab03.metricas import agentes
from lab03.metricas.agentes import (
    AUTORES_BOT,
    AUTORIA,
    BRANCH,
    CAMPOS_ADOCAO,
    CAMPOS_COMMITS_IA,
    LABEL,
    LABELS,
    PREFIXOS_BRANCH,
    Rastro,
    adocao_do_repo,
    ferramenta_do_arquivo,
    ferramenta_do_gitignore,
    marcar_commits,
    resumir_mensagem,
)
from lab03.pipeline.api import ErroAPI, GitHubAPI, RecursoAusente
from lab03.pipeline.coleta import gravar_marcador, ler_marcador, pasta_repo
from lab03.pipeline.runs import _como_intervalo, fatias_mensais, partir

INTERVALO_BUSCA_S = 2.1  # a busca aceita 30 chamadas por minuto
ESPERA_LIMITE_SECUNDARIO_S = 60  # o 403 secundário da busca nem sempre traz Retry-After
TETO_BUSCA = 1000  # a busca não devolve mais que isso, mesmo paginando
POR_PAGINA = 100
MAX_PAGINAS_COMMITS = 30
MAX_PERDIDOS_SEGUIDOS = 3  # mais que isso já não é um commit quebrado, é a API fora

MARCADOR = "_adocao"
ARQUIVO_FALHAS = "_adocao_falhas.json"
# muda quando muda a detecção ou a coleta, e aí o marcador velho é refeito (do cache)
VERSAO_CODIGO = hashlib.sha1(Path(agentes.__file__).read_bytes() + Path(__file__).read_bytes()).hexdigest()[:12]

log = logging.getLogger(__name__)


# ---------- commits ----------

def _commit_enxuto(commit: dict) -> dict:
    if "mensagem" in commit:  # já enxuto; o resumo também encolhe o cache gravado antes dele
        return {**commit, "mensagem": resumir_mensagem(commit["mensagem"])}
    dados = commit["commit"]
    return {
        "sha": commit["sha"],
        # committer: quando o commit entrou no branch, que é o que o `since`/`until` filtra
        "data": dados["committer"]["date"],
        "autor": dados["author"]["name"],
        "login": (commit.get("author") or {}).get("login"),
        "mensagem": resumir_mensagem(dados["message"]),
    }


def _pagina_commits(corpo: list) -> list:
    return [_commit_enxuto(c) for c in corpo]


def _iso(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


class Falhas:
    """Consultas de commits que deram 5xx até desistir, anotadas em disco ao lado do cache.

    Erro não vai para o cache da `GitHubAPI`, então sem isso cada retomada refaria as 5 tentativas
    de cada nível da partição até o commit quebrado (uns 5 min por commit no hermes-agent). Apagar
    o arquivo faz tudo ser tentado de novo.
    """

    def __init__(self, arquivo: Path):
        self.arquivo = arquivo
        self.chaves: set[str] = set(json.loads(arquivo.read_text(encoding="utf-8"))) if arquivo.exists() else set()

    def __contains__(self, chave: str) -> bool:
        return chave in self.chaves

    def anotar(self, chave: str) -> None:
        self.chaves.add(chave)
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.arquivo.with_suffix(".tmp")
        tmp.write_text(json.dumps(sorted(self.chaves)), encoding="utf-8")
        os.replace(tmp, self.arquivo)


def _ja_falhou(caminho: str) -> ErroAPI:
    return ErroAPI(caminho, 0, f"falhou numa execução anterior (ver {ARQUIVO_FALHAS})")


def _um_por_pagina(
    api: GitHubAPI, repo: str, caminho: str, params: dict, falhas: Falhas
) -> tuple[list[dict], int]:
    """Último recurso para um segundo que dá 500 mesmo sozinho: um commit por página.

    No hermes-agent é um commit só que o GitHub não consegue servir (o JSON vem cortado); assim
    ele fica de fora e os vizinhos entram. Devolve os commits e quantas páginas falharam.
    """
    achados: list[dict] = []
    perdidos = seguidos = 0
    pagina = 1
    while True:
        chave = f"{params['since']}..{params['until']}#{pagina}"
        try:
            if chave in falhas:
                raise _ja_falhou(caminho)
            lote = api.get(caminho, {**params, "per_page": 1, "page": pagina}, enxugar=_pagina_commits)
            seguidos = 0
        except ErroAPI as erro:
            seguidos += 1
            if erro.status != 0 or seguidos > MAX_PERDIDOS_SEGUIDOS:
                raise
            falhas.anotar(chave)
            log.warning("%s: commit %d de %s..%s não sai da API (%s), ficando sem ele",
                        repo, pagina, params["since"], params["until"], erro.mensagem)
            perdidos += 1
            lote = [None]
        if not lote:
            return achados, perdidos
        achados.extend(c for c in lote if c is not None)
        pagina += 1


def _commits_do_mes(
    api: GitHubAPI, repo: str, branch: str, mes: tuple[date, date], falhas: Falhas
) -> tuple[list[dict], int]:
    caminho = f"/repos/{repo}/commits"
    pendentes = [_como_intervalo(mes)]
    achados: list[dict] = []
    perdidos = 0
    while pendentes:
        intervalo = pendentes.pop(0)
        params = {"sha": branch, "since": _iso(intervalo[0]), "until": _iso(intervalo[1])}
        divisivel = intervalo[1] - intervalo[0] >= timedelta(seconds=1)
        chave = f"{params['since']}..{params['until']}"
        try:
            if chave in falhas:
                raise _ja_falhou(caminho)
            # mesma chave da 1ª página do paginar, então essa espiada sai do cache depois
            paginas = api.paginas(caminho, {"per_page": POR_PAGINA, **params}, enxugar=_pagina_commits)
            if paginas > MAX_PAGINAS_COMMITS and divisivel:
                log.info("%s: %s..%s tem %d páginas de commits, partindo ao meio",
                         repo, params["since"], params["until"], paginas)
                pendentes[:0] = partir(intervalo)
                continue
            achados.extend(api.paginar(caminho, params, enxugar=_pagina_commits))
        except ErroAPI as erro:
            # status 0 é 5xx ou rede até desistir; um intervalo menor é uma consulta mais leve
            if erro.status != 0:
                raise
            falhas.anotar(chave)
            if divisivel:
                log.warning("%s: %s..%s falhou (%s), partindo ao meio",
                            repo, params["since"], params["until"], erro.mensagem)
                pendentes[:0] = partir(intervalo)
                continue
            lote, sem_resposta = _um_por_pagina(api, repo, caminho, params, falhas)
            achados.extend(lote)
            perdidos += sem_resposta
    return achados, perdidos


def _commits_da_janela_inteira(
    api: GitHubAPI, repo: str, branch: str, inicio: date, fim: date, falhas: Falhas
) -> list[dict]:
    """A janela numa consulta só, se ela cabe em `MAX_PAGINAS_COMMITS` páginas; senão, nada.

    Complementa as fatias mensais. Com datas de committer fora de ordem (merge de branch antigo),
    o `since` faz o /commits parar de andar cedo, como o `git log --since`: no nvm, a fatia de
    setembro trouxe 16 de 33 commits. Numa consulta da janela inteira o `since` fica longe e
    quase nunca corta; nas fatias, o corte de uma não é o da outra. A união pega os dois.
    """
    caminho = f"/repos/{repo}/commits"
    params = {"sha": branch, "since": f"{inicio}T00:00:00Z", "until": f"{fim}T23:59:59Z"}
    chave = f"{params['since']}..{params['until']}"
    try:
        if chave in falhas:
            raise _ja_falhou(caminho)
        if api.paginas(caminho, {"per_page": POR_PAGINA, **params}, enxugar=_pagina_commits) > MAX_PAGINAS_COMMITS:
            return []
        return api.paginar(caminho, params, enxugar=_pagina_commits)
    except ErroAPI as erro:
        if erro.status != 0:
            raise
        falhas.anotar(chave)
        log.warning("%s: janela inteira falhou (%s), ficando só com as fatias mensais", repo, erro.mensagem)
        return []


def listar_commits(api: GitHubAPI, repo: str, branch: str, inicio: date, fim: date) -> tuple[list[dict], int]:
    """Commits do branch na janela, do mais novo para o mais velho, e quantos não saíram da API.
    Repo vazio (409) dá lista vazia.

    A janela vai mês a mês, e o mês com mais de `MAX_PAGINAS_COMMITS` páginas, ou que dá 5xx até
    esgotar as tentativas, é partido ao meio: paginar fundo no /commits dá HTTP 500 (o
    hermes-agent quebrou na página 152 de 476). Um segundo que ainda falha vai um commit por vez.
    Quem cabe em 30 páginas também é consultado de uma vez (`_commits_da_janela_inteira`).
    """
    try:
        falhas = Falhas(pasta_repo(api.pasta_cache, repo) / ARQUIVO_FALHAS)
        meses = [_commits_do_mes(api, repo, branch, mes, falhas) for mes in fatias_mensais(inicio, fim)]
        inteira = _commits_da_janela_inteira(api, repo, branch, inicio, fim, falhas)
    except RecursoAusente:
        return [], 0
    vistos = {c["sha"]: c for lote in [*(lote for lote, _ in meses), inteira] for c in lote}
    return sorted(vistos.values(), key=lambda c: c["data"], reverse=True), sum(p for _, p in meses)


# ---------- arquivos ----------

def _arvore_enxuta(corpo: dict) -> dict:
    """Da árvore inteira (até 100 mil entradas) só ficam os arquivos de agente."""
    return {
        "truncated": corpo.get("truncated", False),
        "tree": [{"path": e["path"]} for e in corpo.get("tree", []) if ferramenta_do_arquivo(e["path"])],
    }


def arquivos_de_agente(api: GitHubAPI, repo: str, ref: str) -> list[str]:
    try:
        corpo = api.get(f"/repos/{repo}/git/trees/{quote(ref, safe='')}", {"recursive": 1},
                        enxugar=_arvore_enxuta)
    except RecursoAusente:
        return []
    if corpo["truncated"]:
        log.warning("%s: árvore truncada pela API, arquivos de agente podem faltar", repo)
    return [e["path"] for e in corpo["tree"]]


def _gitignore_enxuto(corpo: dict) -> dict:
    if "linhas" in corpo:
        return corpo
    # arquivo acima de 1 MB vem sem `content`
    texto = base64.b64decode(corpo.get("content") or "").decode("utf-8", errors="replace")
    return {"linhas": [linha.strip() for linha in texto.splitlines() if ferramenta_do_gitignore(linha)]}


def gitignore_de_agente(api: GitHubAPI, repo: str, ref: str) -> list[str]:
    """Linhas do `.gitignore` da raiz que escondem arquivo de agente."""
    try:
        return api.get(f"/repos/{repo}/contents/.gitignore", {"ref": ref}, enxugar=_gitignore_enxuto)["linhas"]
    except RecursoAusente:
        return []


# ---------- PRs pela busca ----------

def _busca_enxuta(corpo: dict) -> dict:
    return {
        "total_count": corpo["total_count"],
        "items": [
            item if "login" in item else {
                "number": item["number"],
                "login": (item.get("user") or {}).get("login"),
                "labels": [rotulo["name"] for rotulo in item.get("labels", [])],
                "created_at": item["created_at"],
                "merged_at": (item.get("pull_request") or {}).get("merged_at"),
            }
            for item in corpo["items"]
        ],
    }


class Buscador:
    """`/search/issues` com no máximo uma chamada de rede a cada `INTERVALO_BUSCA_S`.

    Página que já está no cache não espera. O 403 do limite secundário vem sem `Retry-After` e
    com cota sobrando, então a `GitHubAPI` o trata como erro comum; aqui ele vira espera.
    """

    def __init__(
        self,
        api: GitHubAPI,
        intervalo: float = INTERVALO_BUSCA_S,
        dormir: Callable[[float], None] = time.sleep,
        agora: Callable[[], float] = time.monotonic,
    ):
        self.api = api
        self.intervalo = intervalo
        self._dormir = dormir
        self._agora = agora
        self._ultima: Optional[float] = None
        self.buscas_rede = 0

    def pagina(self, q: str, pagina: int) -> dict:
        params = {"q": q, "per_page": POR_PAGINA, "page": pagina}
        no_cache = self.api.arquivo_cache("/search/issues", params).exists()
        while True:
            if not no_cache:
                self._esperar_vez()
            try:
                return self.api.get("/search/issues", params, enxugar=_busca_enxuta)
            except ErroAPI as erro:
                # a mensagem vem cortada em 200 caracteres; "secondary" já aparece na URL da doc
                if erro.status != 403 or "secondary" not in erro.mensagem.lower():
                    raise
                log.warning("limite secundário da busca, esperando %ss", ESPERA_LIMITE_SECUNDARIO_S)
                self._dormir(ESPERA_LIMITE_SECUNDARIO_S)

    def _esperar_vez(self) -> None:
        if self._ultima is not None:
            falta = self._ultima + self.intervalo - self._agora()
            if falta > 0:
                self._dormir(falta)
        self._ultima = self._agora()
        self.buscas_rede += 1


def prs_da_busca(buscador: Buscador, repo: str, filtro: str, inicio: date, fim: date) -> list[dict]:
    """PRs do repo criados na janela que casam com `filtro`. Acima de 1.000, parte a janela ao meio."""
    q = f"repo:{repo} is:pr {filtro} created:{inicio}..{fim}"
    primeira = buscador.pagina(q, 1)
    total = primeira["total_count"]
    if total > TETO_BUSCA and inicio < fim:
        meio = inicio + (fim - inicio) // 2
        return (prs_da_busca(buscador, repo, filtro, inicio, meio)
                + prs_da_busca(buscador, repo, filtro, meio + timedelta(days=1), fim))
    itens = list(primeira["items"])
    pagina = 1
    while len(itens) < min(total, TETO_BUSCA):
        pagina += 1
        lote = buscador.pagina(q, pagina)["items"]
        if not lote:
            break
        itens.extend(lote)
    return itens


def filtros_de_busca() -> list[tuple[str, Rastro]]:
    return [
        *((f"head:{prefixo}", Rastro(f, BRANCH)) for prefixo, f in PREFIXOS_BRANCH.items()),
        *((f"label:{rotulo}", Rastro(f, LABEL)) for rotulo, f in LABELS.items()),
        *((f"author:{conta}", Rastro(f, AUTORIA)) for conta, f in AUTORES_BOT.items()),
    ]


def prs_de_agente(buscador: Buscador, repo: str, inicio: date, fim: date) -> Optional[dict[int, list[Rastro]]]:
    """Número do PR -> rastros que o puseram na lista. None se a busca recusou o repo (422)."""
    prs: dict[int, set[Rastro]] = {}
    try:
        for filtro, rastro in filtros_de_busca():
            for item in prs_da_busca(buscador, repo, filtro, inicio, fim):
                prs.setdefault(item["number"], set()).add(rastro)
    except ErroAPI as erro:
        if erro.status != 422:
            raise
        log.warning("%s: busca recusou o repositório (%s), PRs de agente ficam vazios", repo, erro.mensagem)
        return None
    return {numero: sorted(rastros) for numero, rastros in prs.items()}


# ---------- um repo e o fluxo ----------

def coletar_repo(api: GitHubAPI, buscador: Buscador, repo: str, branch: str, inicio: date, fim: date) -> dict:
    commits, perdidos = listar_commits(api, repo, branch, inicio, fim)
    # a árvore do último commit da janela, e não a de hoje, para não contar arquivo criado depois
    ref = commits[0]["sha"] if commits else branch
    return {
        "repo": repo,
        "commits": commits,
        "commits_perdidos": perdidos,
        "arquivos": arquivos_de_agente(api, repo, ref),
        "gitignore": gitignore_de_agente(api, repo, ref),
        "prs": prs_de_agente(buscador, repo, inicio, fim),
    }


def _escrever_csv(caminho: Path, campos: list[str], linhas: list[dict]) -> None:
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(linhas)


def _cota(api: GitHubAPI) -> str:
    return "?" if api.restante is None else str(api.restante)


def _resultado_do_repo(
    api: GitHubAPI, buscador: Buscador, repo: str, branch: str, inicio: date, fim: date
) -> dict:
    """O que vai para o marcador: a linha de adoção e as linhas do `commits_ia.csv`.

    404/409 ou outro 4xx deixam `adocao` None (colunas vazias) e o repo conta como terminado;
    falha de rede que esgotou as tentativas sobe, para ele ser refeito na próxima execução.
    """
    try:
        coleta = coletar_repo(api, buscador, repo, branch, inicio, fim)
    except (RecursoAusente, ErroAPI) as erro:
        if isinstance(erro, ErroAPI) and erro.status < 400:
            raise
        log.warning("%s: %s, adoção fica vazia", repo, erro)
        return {"adocao": None, "commits_ia": []}
    marcados = marcar_commits(coleta["commits"], coleta["prs"] or {})
    linha = adocao_do_repo(coleta["commits"], marcados, coleta["arquivos"], coleta["gitignore"],
                           coleta["prs"], coleta["commits_perdidos"])
    return {"adocao": linha, "commits_ia": [{**m, "repo": repo} for m in marcados]}


def salvar_csvs(pasta: Path, campos: list[str], linhas: list[dict], resultados: dict[str, dict]) -> None:
    vazio = dict.fromkeys(CAMPOS_ADOCAO)
    _escrever_csv(pasta / "repos.csv", [*campos, *CAMPOS_ADOCAO],
                  [{**linha, **vazio, **(resultados.get(linha["repo"], {}).get("adocao") or {})}
                   for linha in linhas])
    _escrever_csv(pasta / "commits_ia.csv", list(CAMPOS_COMMITS_IA),
                  [m for linha in linhas for m in resultados.get(linha["repo"], {}).get("commits_ia", [])])


def executar(
    api: GitHubAPI,
    inicio: date,
    fim: date,
    pasta_saida: str | Path,
    limite: Optional[int] = None,
    buscador: Optional[Buscador] = None,
    so_concluidos: bool = False,
) -> dict[str, dict]:
    """Coleta os `limite` primeiros repositórios do `repos.csv` (todos, sem limite) e grava os CSVs.

    Os CSVs saem no fim e também quando a execução para no meio, só com os repos terminados.
    `so_concluidos` não chama a API: grava os CSVs com quem já tem marcador.
    """
    pasta = Path(pasta_saida)
    with (pasta / "repos.csv").open(encoding="utf-8", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        campos = [c for c in leitor.fieldnames or [] if c not in CAMPOS_ADOCAO]
        linhas = list(leitor)
    buscador = buscador or Buscador(api)
    alvo = linhas[:limite] if limite else linhas
    assinatura = {"inicio": str(inicio), "fim": str(fim), "codigo": VERSAO_CODIGO}

    resultados: dict[str, dict] = {}
    try:
        for i, linha in enumerate(alvo, start=1):
            repo = linha["repo"]
            resultado = ler_marcador(api.pasta_cache, repo, assinatura, MARCADOR)
            if resultado is None and so_concluidos:
                continue
            if resultado is None:
                log.info("adoção %d/%d %s | cota %s", i, len(alvo), repo, _cota(api))
                resultado = _resultado_do_repo(api, buscador, repo, linha["default_branch"], inicio, fim)
                gravar_marcador(api.pasta_cache, repo, assinatura, resultado, MARCADOR)
                if resultado["adocao"]:
                    log.info("adoção %d/%d %s -> %d de %d commits com IA | cota %s", i, len(alvo), repo,
                             resultado["adocao"]["commits_ia"], resultado["adocao"]["commits_janela"], _cota(api))
            resultados[repo] = resultado
    finally:
        salvar_csvs(pasta, campos, linhas, resultados)
        log.info("%d de %d repositórios com adoção concluída nos CSVs, %d buscas de rede",
                 len(resultados), len(alvo), buscador.buscas_rede)
    return {repo: r["adocao"] for repo, r in resultados.items() if r["adocao"]}

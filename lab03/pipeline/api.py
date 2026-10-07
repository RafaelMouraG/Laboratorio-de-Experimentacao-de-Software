"""Acesso à API REST do GitHub com cache em disco, retomada e espera de rate limit.

Toda resposta (inclusive 404/409) vira um JSON em `pasta_cache`. Rodar o pipeline de novo lê do
disco em vez da rede, então um Ctrl+C ou uma cota estourada custam no máximo a página corrente.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import parse_qsl, urlsplit

import requests
from dotenv import load_dotenv

BASE = "https://api.github.com"
MAX_TENTATIVAS = 5
FOLGA_RESET_S = 5
STATUS_AUSENTE = (404, 409)  # tag apagada no compare / repositório vazio

log = logging.getLogger(__name__)


class RecursoAusente(Exception):
    """404 ou 409: não adianta repetir, e a resposta fica no cache para não insistir."""

    def __init__(self, caminho: str, status: int):
        super().__init__(f"{status} em {caminho}")
        self.caminho = caminho
        self.status = status


class ErroAPI(Exception):
    """Resposta de erro que não é rate limit nem falha temporária (ex.: 403 de lista grande)."""

    def __init__(self, caminho: str, status: int, mensagem: str):
        super().__init__(f"{status} em {caminho}: {mensagem}")
        self.caminho = caminho
        self.status = status
        self.mensagem = mensagem


def links(cabecalho: Optional[str]) -> dict[str, str]:
    """`<url>; rel="next", <url>; rel="last"` -> {"next": url, "last": url}."""
    if not cabecalho:
        return {}
    return {rel: url for url, rel in re.findall(r'<([^>]+)>;\s*rel="(\w+)"', cabecalho)}


def _separar_url(url: str) -> tuple[str, dict]:
    partes = urlsplit(url)
    return partes.path, dict(parse_qsl(partes.query))


class GitHubAPI:
    def __init__(
        self,
        token: str,
        pasta_cache: str | Path,
        sessao: Optional[requests.Session] = None,
        dormir: Callable[[float], None] = time.sleep,
        agora: Callable[[], float] = time.time,
    ):
        self.pasta_cache = Path(pasta_cache)
        self.sessao = sessao or requests.Session()
        self.sessao.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        self._dormir = dormir
        self._agora = agora
        self.restante: Optional[int] = None
        self.reset_em: Optional[float] = None
        self.chamadas_rede = 0

    @classmethod
    def do_ambiente(cls, pasta_cache: str | Path, **kwargs) -> "GitHubAPI":
        load_dotenv()
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise SystemExit("GITHUB_TOKEN não definido. Coloque o token no .env da raiz.")
        return cls(token, pasta_cache, **kwargs)

    # ---------- interface usada pelo pipeline ----------

    def get(self, caminho: str, params: Optional[dict] = None) -> Any:
        return self._resposta(caminho, params)["corpo"]

    def paginar(self, caminho: str, params: Optional[dict] = None, chave: Optional[str] = None) -> list:
        """Junta todas as páginas seguindo `Link rel="next"`.

        `chave` diz qual campo tem a lista quando ela vem embrulhada
        (`items` no /search, `workflow_runs` no /actions/runs, `workflows` no /actions/workflows).
        """
        params = {"per_page": 100, **(params or {})}
        itens: list = []
        while True:
            resp = self._resposta(caminho, params)
            corpo = resp["corpo"]
            itens.extend(corpo[chave] if chave else corpo)
            proxima = links(resp["link"]).get("next")
            if not proxima:
                return itens
            caminho, params = _separar_url(proxima)

    def ultima_pagina(self, caminho: str, params: Optional[dict] = None) -> int:
        """Número da última página. Com `per_page=1`, é o total de itens sem baixar a lista."""
        resp = self._resposta(caminho, params)
        ultima = links(resp["link"]).get("last")
        if ultima:
            return int(_separar_url(ultima)[1]["page"])
        corpo = resp["corpo"]
        return len(corpo) if isinstance(corpo, list) else 0

    def cota(self) -> dict:
        """`/rate_limit` não gasta cota, então nunca passa pelo cache."""
        r = self.sessao.get(BASE + "/rate_limit", timeout=30)
        r.raise_for_status()
        return r.json()["resources"]

    # ---------- cache ----------

    def arquivo_cache(self, caminho: str, params: Optional[dict]) -> Path:
        partes = caminho.strip("/").split("/")
        if partes[0] == "repos" and len(partes) >= 3:
            pasta = f"{partes[1]}__{partes[2]}"
            endpoint = "_".join(partes[3:]) or "repo"
        else:
            pasta = "_global"
            endpoint = "_".join(partes)
        endpoint = re.sub(r"[^\w.-]", "-", endpoint)[:60]
        chave = json.dumps([caminho, sorted((params or {}).items())], default=str)
        resumo = hashlib.sha1(chave.encode()).hexdigest()[:12]
        return self.pasta_cache / pasta / f"{endpoint}__{resumo}.json"

    def _ler_cache(self, arquivo: Path) -> Optional[dict]:
        if not arquivo.exists():
            return None
        try:
            return json.loads(arquivo.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("cache corrompido, refazendo: %s", arquivo)
            return None

    def _gravar_cache(self, arquivo: Path, conteudo: dict) -> None:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        tmp = arquivo.with_suffix(".tmp")
        tmp.write_text(json.dumps(conteudo, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, arquivo)

    def _resposta(self, caminho: str, params: Optional[dict]) -> dict:
        arquivo = self.arquivo_cache(caminho, params)
        resp = self._ler_cache(arquivo)
        if resp is None:
            resp = self._buscar(caminho, params)
            self._gravar_cache(arquivo, resp)
        if resp["status"] in STATUS_AUSENTE:
            raise RecursoAusente(caminho, resp["status"])
        return resp

    # ---------- rede ----------

    def _buscar(self, caminho: str, params: Optional[dict]) -> dict:
        tentativa = 0
        while True:
            self._esperar_cota()
            try:
                r = self.sessao.get(BASE + caminho, params=params, timeout=30)
            except (requests.ConnectionError, requests.Timeout) as erro:
                tentativa = self._backoff(caminho, tentativa, str(erro))
                continue
            self.chamadas_rede += 1
            self._anotar_cota(r)

            if r.status_code in (403, 429) and self._eh_rate_limit(r):
                continue
            if r.status_code >= 500:
                tentativa = self._backoff(caminho, tentativa, f"HTTP {r.status_code}")
                continue
            if r.status_code in STATUS_AUSENTE:
                return {"status": r.status_code, "corpo": None, "link": None}
            if r.status_code >= 400:
                raise ErroAPI(caminho, r.status_code, r.text[:200])
            return {"status": r.status_code, "corpo": r.json() if r.content else None, "link": r.headers.get("Link")}

    def _backoff(self, caminho: str, tentativa: int, motivo: str) -> int:
        tentativa += 1
        if tentativa >= MAX_TENTATIVAS:
            raise ErroAPI(caminho, 0, f"desisti depois de {tentativa} tentativas ({motivo})")
        espera = 2 ** (tentativa - 1)
        log.warning("%s em %s, tentando de novo em %ss", motivo, caminho, espera)
        self._dormir(espera)
        return tentativa

    def _anotar_cota(self, r: requests.Response) -> None:
        if "X-RateLimit-Remaining" in r.headers:
            self.restante = int(r.headers["X-RateLimit-Remaining"])
        if "X-RateLimit-Reset" in r.headers:
            self.reset_em = float(r.headers["X-RateLimit-Reset"])

    def _eh_rate_limit(self, r: requests.Response) -> bool:
        """Dorme o necessário e devolve True se o 403/429 era de cota; False se era outra coisa."""
        if "Retry-After" in r.headers:
            espera = float(r.headers["Retry-After"])
            log.warning("limite secundário, esperando %.0fs", espera)
            self._dormir(espera)
            return True
        if self.restante == 0:
            self._esperar_cota()
            return True
        return False

    def _esperar_cota(self) -> None:
        if self.restante != 0 or self.reset_em is None:
            return
        espera = max(self.reset_em - self._agora(), 0) + FOLGA_RESET_S
        log.warning("cota esgotada, esperando %.0f min até o reset", espera / 60)
        self._dormir(espera)
        self.restante = None

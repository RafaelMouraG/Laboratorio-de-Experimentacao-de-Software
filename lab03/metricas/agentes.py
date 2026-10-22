"""Rastros de agentes de programação (RQ 09), nas quatro famílias de Robbes et al. (2026, seção 4.1).

- **arquivo**: arquivo de instruções do agente na árvore (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`,
  `.cursor/rules`, `.github/copilot-instructions.md`) ou citado no `.gitignore`;
- **autoria**: trailer `Co-authored-by` do agente, "Generated with Claude Code" ou commit/PR
  feito pela conta bot do agente;
- **branch**: PR aberto de um branch com o prefixo do agente (`copilot/`, `codex/`...);
- **label**: PR com o label que o agente põe sozinho (`codex`).

Nada aqui chama a API: as funções recebem o que `pipeline/adocao.py` guardou no cache.
"""

from __future__ import annotations

import re
from typing import Iterable, NamedTuple, Optional

ARQUIVO, AUTORIA, BRANCH, LABEL = "arquivo", "autoria", "branch", "label"

CLAUDE, COPILOT, CURSOR, CODEX, DEVIN = "Claude", "Copilot", "Cursor", "Codex", "Devin"
GENERICO = "genérico"  # AGENTS.md é lido por vários agentes, não dá para dizer qual

# prefixo do branch -> ferramenta. O GitHub casa `head:copilot/` por prefixo.
PREFIXOS_BRANCH = {"copilot/": COPILOT, "codex/": CODEX, "cursor/": CURSOR, "claude/": CLAUDE, "devin/": DEVIN}
LABELS = {"codex": CODEX}
# contas que abrem PR sozinhas, no formato do qualificador `author:` da busca
AUTORES_BOT = {"app/copilot-swe-agent": COPILOT, "app/devin-ai-integration": DEVIN}

# login do autor do commit (minúsculo). `Copilot` é a conta do agente desde 2025; o login antigo
# era `copilot-swe-agent[bot]`. GitHub não deixa conta humana com colchetes nem repetir login.
LOGINS = {
    "copilot": COPILOT,
    "copilot-swe-agent[bot]": COPILOT,
    "devin-ai-integration[bot]": DEVIN,
    "claude[bot]": CLAUDE,
    "cursoragent": CURSOR,
}

_TRAILER = re.compile(r"^[ \t>]*co-authored-by:[ \t]*(.+?)[ \t]*$", re.IGNORECASE | re.MULTILINE)
_GERADO_CLAUDE = re.compile(r"generated with \[?claude code\b", re.IGNORECASE)
_MERGE_PR = re.compile(r"^Merge pull request #(\d+) from [^/\s]+/(\S+)")
_NUMERO_PR = re.compile(r"\(#(\d+)\)\s*$")

# Cada coautor é testado contra estas regras, na ordem. Só nome não basta para o Claude, porque
# há gente chamada Claude: precisa do e-mail da Anthropic ou do nome de um modelo.
_COAUTORES = (
    (re.compile(r"@anthropic\.com>|^claude (code|opus|sonnet|haiku)\b", re.IGNORECASE), CLAUDE),
    (re.compile(r"\+copilot(-swe-agent\[bot\])?@users\.noreply\.github\.com>|^copilot\s*<", re.IGNORECASE), COPILOT),
    (re.compile(r"cursoragent@cursor\.com>|^cursor agent\s*<", re.IGNORECASE), CURSOR),
    (re.compile(r"codex@openai\.com>|noreply@openai\.com>|^(openai )?codex\s*<", re.IGNORECASE), CODEX),
    (re.compile(r"devin-ai-integration\[bot\]", re.IGNORECASE), DEVIN),
)


class Rastro(NamedTuple):
    ferramenta: str
    familia: str


# O que fica da mensagem no cache: a 1ª linha (merge e `(#N)` do squash), toda linha com cara de
# trailer, em qualquer ponto do texto, e toda linha que cita um agente. O resto é prosa que nenhuma
# regra lê, e era quase 80% do espaço (27,9 MB -> 5,7 MB no hermes-agent).
_LINHA_UTIL = re.compile(
    r"^[ \t>]*[A-Za-z][\w-]*:\s|generated with|🤖|claude|copilot|cursor|codex|devin|anthropic|openai|agent",
    re.IGNORECASE,
)


def resumir_mensagem(mensagem: Optional[str]) -> str:
    """Só as linhas que as regras deste módulo podem usar. Aplicar duas vezes não muda nada."""
    primeira, *resto = (mensagem or "").split("\n")
    return "\n".join([primeira, *(linha for linha in resto if _LINHA_UTIL.search(linha))])


def ferramenta_do_coautor(coautor: str) -> Optional[str]:
    """`Claude Opus 5.5 <noreply@anthropic.com>` -> "Claude"; humano -> None."""
    return next((ferramenta for regra, ferramenta in _COAUTORES if regra.search(coautor)), None)


def _ordenar(rastros: Iterable[Rastro]) -> list[Rastro]:
    return sorted(set(rastros))


def rastros_do_commit(commit: dict) -> list[Rastro]:
    """Marcas de agente num commit enxuto (`sha`, `data`, `autor`, `login`, `mensagem`).

    Olha a mensagem inteira, não só o fim: um squash junta as mensagens de vários commits e os
    trailers ficam no meio. Um merge de PR cujo branch tem prefixo de agente conta como família
    branch. Cada par ferramenta/família aparece uma vez só.
    """
    mensagem = commit.get("mensagem") or ""
    rastros = []
    for coautor in _TRAILER.findall(mensagem):
        ferramenta = ferramenta_do_coautor(coautor)
        if ferramenta:
            rastros.append(Rastro(ferramenta, AUTORIA))
    if _GERADO_CLAUDE.search(mensagem):
        rastros.append(Rastro(CLAUDE, AUTORIA))
    for conta in (commit.get("login"), commit.get("autor")):
        ferramenta = LOGINS.get((conta or "").lower())
        if ferramenta:
            rastros.append(Rastro(ferramenta, AUTORIA))
    merge = _MERGE_PR.match(mensagem)
    if merge:
        ferramenta = ferramenta_do_branch(merge.group(2))
        if ferramenta:
            rastros.append(Rastro(ferramenta, BRANCH))
    return _ordenar(rastros)


def ferramenta_do_branch(branch: str) -> Optional[str]:
    return next((f for prefixo, f in PREFIXOS_BRANCH.items() if branch.lower().startswith(prefixo)), None)


def numero_do_pr(mensagem: str) -> Optional[int]:
    """PR de onde o commit veio: `Merge pull request #12 from ...` ou `título (#12)` do squash."""
    primeira = (mensagem or "").split("\n", 1)[0]
    achado = _MERGE_PR.match(primeira) or _NUMERO_PR.search(primeira)
    return int(achado.group(1)) if achado else None


def rastros_do_commit_com_prs(commit: dict, prs: dict[int, list[Rastro]]) -> list[Rastro]:
    """`rastros_do_commit` mais as marcas do PR de onde o commit veio, se ele é PR de agente.

    `prs` vem da busca de issues: número -> rastros (branch, label ou autor bot). É o jeito de
    pegar o squash de um PR do Copilot que não deixou trailer no commit.
    """
    numero = numero_do_pr(commit.get("mensagem") or "")
    return _ordenar([*rastros_do_commit(commit), *prs.get(numero, [])])


def ferramenta_do_arquivo(caminho: str) -> Optional[str]:
    """Arquivo de instruções de agente em qualquer pasta da árvore, ou None."""
    partes = caminho.split("/")
    nome = partes[-1]
    if nome == "CLAUDE.md":
        return CLAUDE
    if nome == "AGENTS.md":
        return GENERICO
    if nome == ".cursorrules" or any(a == ".cursor" and b == "rules" for a, b in zip(partes, partes[1:])):
        return CURSOR
    if caminho == ".github/copilot-instructions.md" or caminho.endswith("/.github/copilot-instructions.md"):
        return COPILOT
    return None


# Padrão do .gitignore que esconde algum dos arquivos acima. `.cursor` inteiro conta porque
# esconde o `.cursor/rules`.
_GITIGNORE = (
    (re.compile(r"(^|/)CLAUDE(\.local)?\.md$|(^|/)CLAUDE\*"), CLAUDE),
    (re.compile(r"(^|/)AGENTS\.md$"), GENERICO),
    (re.compile(r"(^|/)\.cursorrules$|(^|/)\.cursor(/|/rules/?|/\*\*?)?$"), CURSOR),
    (re.compile(r"copilot-instructions\.md$"), COPILOT),
)


def ferramenta_do_gitignore(linha: str) -> Optional[str]:
    """`/CLAUDE.md` -> "Claude". Comentário e negação (`!AGENTS.md`) não escondem nada."""
    padrao = linha.strip()
    if not padrao or padrao.startswith(("#", "!")):
        return None
    return next((f for regra, f in _GITIGNORE if regra.search(padrao)), None)


# ---------- agregação por repositório ----------

CAMPOS_COMMITS_IA = ("sha", "repo", "data", "ferramenta", "familia")
CAMPOS_ADOCAO = (
    "commits_janela", "commits_perdidos", "commits_ia", "primeiro_commit_ia", "proporcao_ia_desde_adocao",
    "prs_agente", "arquivo_agente", "arquivo_agente_gitignore", "ferramentas_ia",
)


def marcar_commits(commits: list[dict], prs: dict[int, list[Rastro]]) -> list[dict]:
    """Uma linha por par commit/rastro, para o `commits_ia.csv`. Commit sem marca não entra."""
    return [
        {"sha": c["sha"], "data": c["data"], "ferramenta": r.ferramenta, "familia": r.familia}
        for c in commits
        for r in rastros_do_commit_com_prs(c, prs)
    ]


def adocao_do_repo(
    commits: list[dict],
    marcados: list[dict],
    arquivos: list[str],
    gitignore: list[str],
    prs: Optional[dict[int, list[Rastro]]],
    perdidos: int = 0,
) -> dict:
    """Colunas de adoção do `repos.csv`.

    A proporção conta a partir do primeiro commit com IA (inclusive): antes dele o repositório
    ainda não tinha adotado, e diluir com esse período misturaria adoção tardia com uso raro.
    `prs` None quer dizer que a busca falhou; aí `prs_agente` fica vazio, não zero. `perdidos` são
    commits que a API não conseguiu devolver e que ficam fora de todas as contas.
    """
    shas_ia = {m["sha"] for m in marcados}
    primeiro = min((m["data"] for m in marcados), default=None)
    desde = sum(1 for c in commits if primeiro is not None and c["data"] >= primeiro)
    ferramentas = {m["ferramenta"] for m in marcados}
    ferramentas |= {r.ferramenta for rastros in (prs or {}).values() for r in rastros}
    ferramentas |= {f for f in map(ferramenta_do_arquivo, arquivos) if f}
    ferramentas |= {f for f in map(ferramenta_do_gitignore, gitignore) if f}
    return {
        "commits_janela": len(commits),
        "commits_perdidos": perdidos,
        "commits_ia": len(shas_ia),
        "primeiro_commit_ia": primeiro,
        "proporcao_ia_desde_adocao": len(shas_ia) / desde if desde else None,
        "prs_agente": None if prs is None else len(prs),
        "arquivo_agente": bool(arquivos),
        "arquivo_agente_gitignore": bool(gitignore),
        "ferramentas_ia": ";".join(sorted(ferramentas)),
    }

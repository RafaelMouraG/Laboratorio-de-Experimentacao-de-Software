import pytest

from lab03.metricas.agentes import (
    AUTORIA,
    BRANCH,
    CLAUDE,
    CODEX,
    COPILOT,
    CURSOR,
    DEVIN,
    GENERICO,
    LABEL,
    Rastro,
    adocao_do_repo,
    ferramenta_do_arquivo,
    ferramenta_do_gitignore,
    marcar_commits,
    numero_do_pr,
    rastros_do_commit,
    rastros_do_commit_com_prs,
    resumir_mensagem,
)


def commit(mensagem, sha="s1", data="2026-01-10T00:00:00Z", autor="Ana", login="ana"):
    return {"sha": sha, "data": data, "autor": autor, "login": login, "mensagem": mensagem}


@pytest.mark.parametrize("mensagem, ferramenta", [
    ("feat: x\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>", CLAUDE),
    ("feat: x\n\nCo-Authored-By: Claude <noreply@anthropic.com>", CLAUDE),
    ("fix: y (#3)\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>", COPILOT),
    ("fix: y\n\nCo-authored-by: copilot-swe-agent[bot] <198982749+Copilot@users.noreply.github.com>", COPILOT),
    ("chore: z\n\nCo-authored-by: Cursor Agent <cursoragent@cursor.com>", CURSOR),
    ("chore: z\n\nCo-authored-by: Codex <codex@openai.com>", CODEX),
    ("docs\n\nCo-authored-by: devin-ai-integration[bot] <158243242+devin-ai-integration[bot]@users.noreply.github.com>",
     DEVIN),
])
def test_trailer_de_cada_ferramenta(mensagem, ferramenta):
    assert rastros_do_commit(commit(mensagem)) == [Rastro(ferramenta, AUTORIA)]


def test_generated_with_claude_code_sem_trailer():
    mensagem = "refactor\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)"
    assert rastros_do_commit(commit(mensagem)) == [Rastro(CLAUDE, AUTORIA)]


def test_trailer_no_meio_do_texto_de_um_squash():
    mensagem = (
        "Juntar tudo (#42)\n\n* primeiro passo\n\nCo-authored-by: Claude Sonnet 5.5 <noreply@anthropic.com>\n\n"
        "* segundo passo\n\nmais texto depois do trailer"
    )
    assert rastros_do_commit(commit(mensagem)) == [Rastro(CLAUDE, AUTORIA)]


@pytest.mark.parametrize("login, autor, ferramenta", [
    ("Copilot", "Copilot", COPILOT),
    ("copilot-swe-agent[bot]", "copilot-swe-agent[bot]", COPILOT),
    ("devin-ai-integration[bot]", "devin-ai-integration[bot]", DEVIN),
    (None, "devin-ai-integration[bot]", DEVIN),  # e-mail sem conta: login vem vazio
])
def test_commit_feito_pela_conta_do_agente(login, autor, ferramenta):
    assert rastros_do_commit(commit("fix", autor=autor, login=login)) == [Rastro(ferramenta, AUTORIA)]


def test_commit_sem_marca():
    assert rastros_do_commit(commit("fix: corrige o parser\n\nCo-authored-by: Bia <bia@x.com>")) == []
    assert rastros_do_commit({"sha": "s", "data": "d", "autor": None, "login": None, "mensagem": None}) == []


@pytest.mark.parametrize("mensagem", [
    "feat: integra a API do claude no chat",
    "Bump anthropic from 0.40 to 0.41\n\nUpdates claude code examples",
    "fix\n\nCo-authored-by: Claude Monet <claude.monet@example.com>",
    "docs: explica Co-authored-by: Claude no README",  # trailer só vale no início da linha
])
def test_palavra_claude_num_commit_qualquer_nao_conta(mensagem):
    assert rastros_do_commit(commit(mensagem)) == []


def test_duas_marcas_da_mesma_familia_viram_uma_e_ferramentas_diferentes_ficam():
    mensagem = (
        "feat\n\n🤖 Generated with [Claude Code](https://claude.ai/code)\n\n"
        "Co-Authored-By: Claude <noreply@anthropic.com>\n"
        "Co-authored-by: Copilot <1+Copilot@users.noreply.github.com>"
    )
    assert rastros_do_commit(commit(mensagem)) == [Rastro(CLAUDE, AUTORIA), Rastro(COPILOT, AUTORIA)]


def test_merge_de_branch_de_agente_e_familia_branch():
    mensagem = "Merge pull request #7 from fulano/copilot/fix-login\n\nFix login"
    assert rastros_do_commit(commit(mensagem)) == [Rastro(COPILOT, BRANCH)]
    assert rastros_do_commit(commit("Merge pull request #8 from fulano/feature/x")) == []


@pytest.mark.parametrize("mensagem, numero", [
    ("Merge pull request #7 from o/codex/x", 7),
    ("Corrige o build (#1234)\n\ncorpo", 1234),
    ("Corrige o build (#12) e mais", None),
    ("sem pr", None),
    (None, None),
])
def test_numero_do_pr(mensagem, numero):
    assert numero_do_pr(mensagem) == numero


def test_squash_de_pr_de_agente_herda_os_rastros_do_pr():
    prs = {12: [Rastro(CODEX, BRANCH), Rastro(CODEX, LABEL)]}
    assert rastros_do_commit_com_prs(commit("Faz x (#12)"), prs) == [Rastro(CODEX, BRANCH), Rastro(CODEX, LABEL)]
    assert rastros_do_commit_com_prs(commit("Faz y (#13)"), prs) == []


@pytest.mark.parametrize("caminho, ferramenta", [
    ("CLAUDE.md", CLAUDE),
    ("packages/web/CLAUDE.md", CLAUDE),
    ("AGENTS.md", GENERICO),
    (".cursorrules", CURSOR),
    (".cursor/rules", CURSOR),
    (".cursor/rules/python.mdc", CURSOR),
    (".github/copilot-instructions.md", COPILOT),
    ("docs/.github/copilot-instructions.md", COPILOT),
    ("docs/copilot-instructions.md", None),
    (".cursor/settings.json", None),
    ("claude.md", None),
    ("README.md", None),
])
def test_ferramenta_do_arquivo(caminho, ferramenta):
    assert ferramenta_do_arquivo(caminho) == ferramenta


@pytest.mark.parametrize("linha, ferramenta", [
    ("CLAUDE.md", CLAUDE),
    ("/CLAUDE.local.md", CLAUDE),
    ("AGENTS.md", GENERICO),
    (".cursor/", CURSOR),
    (".cursor", CURSOR),
    ("/.cursorrules", CURSOR),
    (".github/copilot-instructions.md", COPILOT),
    ("# CLAUDE.md", None),
    ("!AGENTS.md", None),
    ("node_modules/", None),
    ("", None),
])
def test_ferramenta_do_gitignore(linha, ferramenta):
    assert ferramenta_do_gitignore(linha) == ferramenta


def test_adocao_conta_a_partir_do_primeiro_commit_com_ia():
    commits = [
        commit("a", sha="a", data="2026-01-01T00:00:00Z"),
        commit("b\n\nCo-Authored-By: Claude <noreply@anthropic.com>", sha="b", data="2026-02-01T00:00:00Z"),
        commit("c", sha="c", data="2026-03-01T00:00:00Z"),
        commit("d (#5)", sha="d", data="2026-04-01T00:00:00Z"),
    ]
    prs = {5: [Rastro(COPILOT, BRANCH)], 9: [Rastro(DEVIN, AUTORIA)]}
    marcados = marcar_commits(commits, prs)
    assert marcados == [
        {"sha": "b", "data": "2026-02-01T00:00:00Z", "ferramenta": CLAUDE, "familia": AUTORIA},
        {"sha": "d", "data": "2026-04-01T00:00:00Z", "ferramenta": COPILOT, "familia": BRANCH},
    ]
    linha = adocao_do_repo(commits, marcados, ["AGENTS.md"], [".cursor/"], prs)
    assert linha == {
        "commits_janela": 4,
        "commits_perdidos": 0,
        "commits_ia": 2,
        "primeiro_commit_ia": "2026-02-01T00:00:00Z",
        "proporcao_ia_desde_adocao": pytest.approx(2 / 3),
        "prs_agente": 2,
        "arquivo_agente": True,
        "arquivo_agente_gitignore": True,
        "ferramentas_ia": "Claude;Copilot;Cursor;Devin;genérico",
    }


def test_adocao_sem_nenhum_rastro_e_busca_que_falhou():
    linha = adocao_do_repo([commit("a")], [], [], [], None)
    assert linha["commits_ia"] == 0
    assert linha["primeiro_commit_ia"] is None
    assert linha["proporcao_ia_desde_adocao"] is None
    assert linha["prs_agente"] is None
    assert linha["arquivo_agente"] is False
    assert linha["ferramentas_ia"] == ""


def test_resumo_da_mensagem_guarda_o_que_as_regras_leem_e_tira_a_prosa():
    mensagem = (
        "Juntar tudo (#42)\n\n* primeiro passo, com uma explicação longa\n"
        "Co-authored-by: Claude Sonnet 5.5 <noreply@anthropic.com>\n"
        "texto qualquer no meio\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n"
        "Signed-off-by: Ana <ana@x.com>"
    )
    resumo = resumir_mensagem(mensagem)
    assert resumo == (
        "Juntar tudo (#42)\nCo-authored-by: Claude Sonnet 5.5 <noreply@anthropic.com>\n"
        "🤖 Generated with [Claude Code](https://claude.com/claude-code)\nSigned-off-by: Ana <ana@x.com>"
    )
    assert resumir_mensagem(resumo) == resumo
    assert rastros_do_commit(commit(resumo)) == rastros_do_commit(commit(mensagem))
    assert resumir_mensagem(None) == ""

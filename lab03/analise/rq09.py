"""RQ 09, análise 1: adoção de agentes de IA × desempenho DORA entre repositórios (#118).

Execute da raiz do repositório com ``python -m lab03.analise.rq09``.

A regra e os cortes dos níveis estão em ``rq09_niveis.py``, commitados antes deste arquivo. Aqui:

1. Spearman da % contínua de commits com IA (``proporcao``) contra cada métrica DORA da RQ 06, com
   Holm sobre as quatro métricas. Recortes: todos os classificados (nenhuma conta como 0%) e só os
   adotantes.
2. Kruskal-Wallis + epsilon² entre nenhuma / baixa / alta da C1, e delta de Cliff entre os pares de
   grupos.
3. Adoção (grupos da C1) como mais um fator da RQ 06, dentro do mesmo Holm dos fatores dela. As
   saídas da RQ 06 não mudam; o resultado vai para ``rq09_rq06_*``.
4. O teste do item 2 refeito com C1 a C4, para ver se sinal e significância se mantêm.
5. Robustez: itens 1 e 2 sem os repositórios que são ferramentas de IA (``FERRAMENTAS_IA``).

Os 2 repositórios com menos de 10 commits depois da adoção ficam fora de tudo (ver o funil da
``rq09_niveis``).
"""

from __future__ import annotations

from itertools import combinations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from statsmodels.stats.multitest import multipletests

from lab03.analise import rq06
from lab03.analise.comum import DADOS, carregar, salvar_figura, salvar_tabela
from lab03.analise.estatistica import cliffs_delta, comparar_grupos, magnitude
from lab03.analise.rq05 import correlacao
from lab03.analise.rq09_niveis import CLASSIFICACOES, GRUPOS, classificar

ALFA = 0.05
METRICAS = rq06.METRICAS
FATOR_ADOCAO = "adocao_c1"
ORDEM_GRUPOS = tuple(GRUPOS.values())  # nenhuma, baixa, alta

PROGRAMACAO = "agente de programação"
LLM = "agente ou assistente de LLM"
# Repositórios cujo produto é um agente de IA. Lista feita à mão pelo nome, pela descrição e pelos
# tópicos do cache de metadados (``lab03/data/cache/<owner>__<repo>/repo__*.json``); falta o grupo
# confirmar o critério. Ficaram de fora, de propósito, editores com IA embutida (vscode, zed),
# servidores de inferência (vllm, llama.cpp, sglang, LocalAI), bibliotecas que só chamam LLM e
# ferramentas que preparam dados para IA (firecrawl, docling, MinerU).
FERRAMENTAS_IA = {
    "anomalyco/opencode": (PROGRAMACAO, "descrição: agente de programação open source"),
    "openai/codex": (PROGRAMACAO, "descrição: agente de programação no terminal"),
    "google-gemini/gemini-cli": (PROGRAMACAO, "descrição: agente de IA do Gemini no terminal"),
    "cline/cline": (PROGRAMACAO, "descrição: agente de programação autônomo (SDK, extensão de IDE, CLI)"),
    "OpenHands/OpenHands": (PROGRAMACAO, "descrição: desenvolvimento feito por IA"),
    "openinterpreter/openinterpreter": (PROGRAMACAO, "descrição: agente de programação para modelos abertos"),
    "aaif-goose/goose": (PROGRAMACAO, "descrição: agente que instala, executa, edita e testa código"),
    "warpdotdev/warp": (PROGRAMACAO, "descrição: ambiente de desenvolvimento agêntico"),
    "earendil-works/pi": (PROGRAMACAO, "descrição: toolkit de agente com CLI de programação"),
    "farion1231/cc-switch": (PROGRAMACAO, "descrição: assistente para Claude Code, Codex e OpenCode"),
    "thedotmack/claude-mem": (PROGRAMACAO, "descrição e tópicos: memória entre sessões do Claude Code"),
    "ruvnet/ruflo": (PROGRAMACAO, "descrição: harness de agentes; tópicos claude e codex"),
    "github/spec-kit": (PROGRAMACAO, "descrição e tópicos: desenvolvimento guiado por spec com Copilot"),
    "Fission-AI/OpenSpec": (PROGRAMACAO, "descrição: desenvolvimento guiado por spec para assistentes de programação"),
    "bmad-code-org/BMAD-METHOD": (PROGRAMACAO, "descrição: método de desenvolvimento ágil guiado por IA"),
    "upstash/context7": (PROGRAMACAO, "descrição: documentação para LLMs e editores de código com IA"),
    "ChromeDevTools/chrome-devtools-mcp": (PROGRAMACAO, "descrição: Chrome DevTools para agentes de programação"),
    "NousResearch/hermes-agent": (LLM, "nome e tópicos: agente de IA geral"),
    "Significant-Gravitas/AutoGPT": (LLM, "nome e tópicos: plataforma de agentes"),
    "langgenius/dify": (LLM, "descrição: workflows agênticos e RAG"),
    "open-webui/open-webui": (LLM, "descrição: interface de chat para LLMs"),
    "langflow-ai/langflow": (LLM, "descrição: construção de agentes e workflows de IA"),
    "langchain-ai/langchain": (LLM, "descrição: plataforma de engenharia de agentes"),
    "langchain-ai/langgraph": (LLM, "descrição: framework de agentes"),
    "browser-use/browser-use": (LLM, "descrição: agentes que usam o navegador"),
    "CherryHQ/cherry-studio": (LLM, "descrição: chat com LLMs e agentes autônomos"),
    "crewAIInc/crewAI": (LLM, "descrição: orquestração de agentes de IA"),
    "agno-agi/agno": (LLM, "descrição: plataforma de agentes"),
    "mem0ai/mem0": (LLM, "descrição: camada de memória para agentes de IA"),
    "Mintplex-Labs/anything-llm": (LLM, "nome e descrição: agente local com LLM"),
    "xtekky/gpt4free": (LLM, "descrição: acesso a vários modelos de linguagem"),
    "infiniflow/ragflow": (LLM, "descrição: motor de RAG com agentes"),
    "run-llama/llama_index": (LLM, "tópicos: framework de agentes e RAG"),
    "CopilotKit/CopilotKit": (LLM, "descrição: frontend para agentes"),
    "khoj-ai/khoj": (LLM, "descrição: assistente de IA com agentes"),
    "AstrBotDevs/AstrBot": (LLM, "descrição: assistente e framework de agentes de IA"),
    "zhayujie/CowAgent": (LLM, "descrição: assistente pessoal de IA e harness de agentes"),
    "danielmiessler/Fabric": (LLM, "descrição: framework de prompts de IA"),
    "janhq/jan": (LLM, "descrição: alternativa offline ao ChatGPT"),
    "ItzCrazyKns/Vane": (LLM, "descrição: motor de respostas com IA"),
    "lfnovo/open-notebook": (LLM, "descrição: implementação aberta do Notebook LM"),
    "HKUDS/LightRAG": (LLM, "descrição: RAG"),
    "VectifyAI/PageIndex": (LLM, "descrição e tópicos: RAG para agentes"),
    "stanfordnlp/dspy": (LLM, "descrição: framework para programar modelos de linguagem"),
    "BerriAI/litellm": (LLM, "descrição: gateway para APIs de LLM"),
    "moeru-ai/airi": (LLM, "descrição e tópicos: companheiro de IA"),
    "modelcontextprotocol/servers": (LLM, "nome: servidores MCP para LLMs"),
    "microsoft/playwright-mcp": (LLM, "nome: servidor MCP do Playwright para agentes"),
}
RECORTES_ROBUSTEZ = {
    "todos": (),
    f"sem {PROGRAMACAO}": (PROGRAMACAO,),
    f"sem {PROGRAMACAO} e {LLM}": (PROGRAMACAO, LLM),
}


def ferramentas_ia() -> pd.DataFrame:
    return pd.DataFrame([{"repo": repo, "categoria": categoria, "motivo": motivo}
                         for repo, (categoria, motivo) in FERRAMENTAS_IA.items()])


def preparar(df: pd.DataFrame, tirar_excluidos: bool = True) -> pd.DataFrame:
    """Junta os níveis de ``rq09_niveis`` ao ``carregar()`` e tira os excluídos.

    As colunas de grupo (``C1_grupo`` ...) viram texto ordenado nenhuma < baixa < alta, e
    ``adocao_c1`` é a ``C1_grupo``, o fator que entra na RQ 06. Com ``tirar_excluidos=False`` os
    excluídos ficam, com níveis vazios, para os outros fatores da RQ 06 usarem os 310 repositórios.
    """
    niveis = classificar(df)
    colunas = ["repo", "proporcao", "excluido", *CLASSIFICACOES, *(f"{c}_grupo" for c in CLASSIFICACOES)]
    df = df.merge(niveis[colunas], on="repo", how="left", validate="one_to_one")
    df = df[~df["excluido"]].copy() if tirar_excluidos else df.copy()
    for nome in CLASSIFICACOES:
        df[f"{nome}_grupo"] = pd.Categorical(df[f"{nome}_grupo"].map(GRUPOS), categories=ORDEM_GRUPOS, ordered=True)
    df[FATOR_ADOCAO] = df["C1_grupo"]
    df["adotante"] = df["commits_ia"] > 0
    return df


def _holm(tabela: pd.DataFrame, coluna: str = "p_valor") -> pd.DataFrame:
    rejeita, ajustado, _, _ = multipletests(tabela[coluna], alpha=ALFA, method="holm")
    tabela["p_holm"] = ajustado
    tabela["significativo"] = rejeita
    return tabela


def spearman(df: pd.DataFrame) -> pd.DataFrame:
    """Spearman da % contra cada métrica, com Holm sobre as métricas dentro de cada recorte."""
    partes = []
    for recorte, dados in (("classificados", df), ("adotantes", df[df["adotante"]])):
        tabela = pd.DataFrame([{"recorte": recorte, **correlacao(dados, "proporcao", m)} for m in METRICAS])
        partes.append(_holm(tabela))
    return pd.concat(partes, ignore_index=True)


def deltas(df: pd.DataFrame, fator: str, metrica: str) -> dict:
    """Delta de Cliff entre cada par de grupos, positivo quando o grupo mais adotante tem valor maior."""
    linha = {}
    for menor, maior in combinations(ORDEM_GRUPOS, 2):
        x = df.loc[df[fator] == maior, metrica].dropna()
        y = df.loc[df[fator] == menor, metrica].dropna()
        linha[f"delta_{maior}_{menor}"] = cliffs_delta(x, y) if len(x) and len(y) else float("nan")
    return linha


def medianas(df: pd.DataFrame, fator: str, metrica: str) -> dict:
    grupos = df.groupby(fator, observed=False)[metrica]
    return {**{f"n_{g}": int(n) for g, n in grupos.count().items()},
            **{f"mediana_{g}": m for g, m in grupos.median().items()}}


def por_nivel(df: pd.DataFrame, classificacao: str = "C1") -> pd.DataFrame:
    """Kruskal-Wallis entre nenhuma / baixa / alta, deltas entre pares e Spearman nos níveis próprios."""
    fator = f"{classificacao}_grupo"
    linhas = []
    for metrica in METRICAS:
        teste = comparar_grupos(df, fator, metrica)
        ordinal = correlacao(df, classificacao, metrica)
        linhas.append({
            "classificacao": classificacao,
            "metrica": metrica,
            "n": teste["n"],
            "h": teste["estatistica"],
            "p_valor": teste["p_valor"],
            "epsilon2": teste["efeito"],
            **deltas(df, fator, metrica),
            "rho_niveis": ordinal["rho"],
            "p_rho_niveis": ordinal["p_valor"],
            **medianas(df, fator, metrica),
        })
    return _holm(pd.DataFrame(linhas))


def com_c1_a_c4(df: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([por_nivel(df, nome) for nome in CLASSIFICACOES], ignore_index=True)


def fator_rq06(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Testes da RQ 06 com a adoção como quinto fator, todos no mesmo Holm, e os deltas extremos.

    Espera ``preparar(..., tirar_excluidos=False)``: os quartis e os outros fatores saem dos mesmos
    repositórios da RQ 06, e só o teste da adoção perde os excluídos (contados em ``ausentes``).
    """
    df = rq06.preparar_fatores(df)
    testes = rq06.testar(df, fatores=(*rq06.FATORES, FATOR_ADOCAO))
    return testes, rq06.direcoes(df, testes)


def robustez(df: pd.DataFrame) -> pd.DataFrame:
    """Spearman e Kruskal-Wallis da C1 sem os repositórios que são ferramentas de IA."""
    categorias = df["repo"].map(lambda r: FERRAMENTAS_IA.get(r, (None, None))[0])
    linhas = []
    for recorte, fora in RECORTES_ROBUSTEZ.items():
        dados = df[~categorias.isin(fora)] if fora else df
        rho = spearman(dados)
        niveis = por_nivel(dados, "C1")
        for metrica in METRICAS:
            todos = rho[(rho["recorte"] == "classificados") & (rho["y"] == metrica)].iloc[0]
            r = rho[(rho["recorte"] == "adotantes") & (rho["y"] == metrica)].iloc[0]
            k = niveis[niveis["metrica"] == metrica].iloc[0]
            linhas.append({
                "recorte": recorte, "repos": len(dados), "metrica": metrica,
                "rho_classificados": todos["rho"], "p_rho_classificados_holm": todos["p_holm"],
                "n_rho_adotantes": r["n"], "rho_adotantes": r["rho"], "p_rho_adotantes_holm": r["p_holm"],
                "n_kw": k["n"], "p_kw_holm": k["p_holm"], "epsilon2": k["epsilon2"],
                "delta_alta_nenhuma": k["delta_alta_nenhuma"],
            })
    return pd.DataFrame(linhas)


def figura(df: pd.DataFrame, rho: pd.DataFrame, niveis: pd.DataFrame):
    """Linha de cima: % contínua × métrica nos adotantes. Linha de baixo: boxplot por grupo da C1."""
    fig, eixos = plt.subplots(2, len(METRICAS), figsize=(3.6 * len(METRICAS), 6.4))
    adotantes = df[df["adotante"]]
    for coluna, (metrica, nome) in enumerate(METRICAS.items()):
        cima, baixo = eixos[0, coluna], eixos[1, coluna]
        validos = adotantes[["proporcao", metrica]].dropna()
        cima.scatter(validos["proporcao"] * 100, validos[metrica], s=12, facecolors="none", edgecolors="black",
                     linewidths=0.6)
        cima.set_xscale("log")
        linha = rho[(rho["recorte"] == "adotantes") & (rho["y"] == metrica)].iloc[0]
        cima.set_title(f"adotantes: ρ = {linha['rho']:.2f}, p aj. = {linha['p_holm']:.2g}, n = {linha['n']}", fontsize=9)
        cima.set_xlabel("% de commits com IA (log)", fontsize=8)
        cima.set_ylabel(nome, fontsize=8)

        valores = [df.loc[df["C1_grupo"] == g, metrica].dropna() for g in ORDEM_GRUPOS]
        baixo.boxplot(valores, tick_labels=list(ORDEM_GRUPOS), medianprops={"color": "black"},
                      flierprops={"marker": "o", "markersize": 3, "markerfacecolor": "none"})
        teste = niveis[niveis["metrica"] == metrica].iloc[0]
        baixo.set_title(f"ε² = {teste['epsilon2']:.3f}, p aj. = {teste['p_holm']:.2g}", fontsize=9)
        baixo.set_xlabel("adoção (C1)", fontsize=8)
        baixo.set_ylabel(nome, fontsize=8)
        if metrica in rq06.ESCALA_LOG:
            cima.set_yscale("log")
            baixo.set_yscale("log")
        for eixo in (cima, baixo):
            eixo.tick_params(labelsize=8)
    fig.tight_layout()
    return fig


def main() -> int:
    df = preparar(carregar(DADOS))
    rho = spearman(df)
    niveis = com_c1_a_c4(df)
    c1 = niveis[niveis["classificacao"] == "C1"]
    testes_rq06, direcoes_rq06 = fator_rq06(preparar(carregar(DADOS), tirar_excluidos=False))
    robusto = robustez(df)

    salvar_tabela(rho, "rq09_spearman")
    salvar_tabela(c1, "rq09_kruskal_c1")
    salvar_tabela(niveis, "rq09_classificacoes")
    salvar_tabela(testes_rq06, "rq09_rq06_testes")
    salvar_tabela(direcoes_rq06, "rq09_rq06_direcoes")
    salvar_tabela(ferramentas_ia(), "rq09_ferramentas_ia")
    salvar_tabela(robusto, "rq09_robustez")
    fig = figura(df, rho, c1)
    salvar_figura(fig, "rq09_adocao")
    plt.close(fig)

    pd.set_option("display.width", 250)
    print(f"RQ 09, análise 1: {len(df)} repositórios ({int(df['adotante'].sum())} adotantes)")
    print(rho.to_string(index=False))
    colunas = ["classificacao", "metrica", "n", "h", "p_valor", "p_holm", "epsilon2",
               "delta_alta_nenhuma", "delta_baixa_nenhuma", "delta_alta_baixa", "rho_niveis", "p_rho_niveis"]
    print(niveis[colunas].to_string(index=False))
    adocao = testes_rq06[testes_rq06["fator"] == FATOR_ADOCAO]
    print(f"RQ 06 com adoção: {len(testes_rq06)} testes, {int(testes_rq06['significativo'].sum())} significativos")
    print(adocao.to_string(index=False))
    print(direcoes_rq06.to_string(index=False))
    print(robusto.to_string(index=False))
    for linha in c1.itertuples():
        print(linha.metrica, "alta x nenhuma:", magnitude(linha.delta_alta_nenhuma))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

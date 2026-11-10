"""Monta o dashboard do Lab04 como um único HTML que abre sem servidor."""

from __future__ import annotations

import math
from pathlib import Path
from string import Template

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

from lab04.simulacao import motor, parametros, q2
from lab04.simulacao import reais as testes_reais
from lab04.simulacao.exemplo import SEMENTE
from lab04.simulacao.gerador import cenario_base, efeito_observado, gerar as gerar_amostra
from lab04.simulacao.testes import mann_whitney, welch

REPOSITORIO = "https://github.com/RafaelMouraG/Laboratorio-de-Experimentacao-de-Software"
BOARD = "https://github.com/users/RafaelMouraG/projects/12"
# Publicado pelo .github/workflows/dashboard.yml a cada push na main.
DASHBOARD = "https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/"
DESTINO = Path(__file__).with_name("index.html")

# A identidade dos testes fica aqui e é reutilizada por G2, G3 e G4.
TESTES = {
    "welch": {"nome": "t de Welch", "cor": "#2563eb"},
    "mann_whitney": {"nome": "Mann-Whitney", "cor": "#dc2626"},
}
GRUPOS = {
    "com_bot": {"nome": "Com review do CodeRabbit", "cor": "#7c3aed"},
    "sem_bot": {"nome": "Sem review de bot", "cor": "#059669"},
}
ALFA = 0.05
ALFAS = (0.05, 0.01)
MARGEM_G3 = {0.05: 0.004, 0.01: 0.002}
SITUACOES = {
    "base": "Cenário base",
    "assimetria": "Assimetria",
    "outliers": "Outliers",
    "n_pequeno": "n pequeno",
    "dispersoes": "Dispersões*",
}

MODELO = Template("""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lab04: Testes de Hipótese</title>
<style>
:root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, sans-serif; color: #172033; background: #f4f7fb; }
* { box-sizing: border-box; }
body { margin: 0; }
header { padding: 3.5rem max(1.25rem, calc((100% - 1180px) / 2)); color: white; background: linear-gradient(135deg, #111827, #293b63); }
header h1 { max-width: 850px; margin: 0 0 .8rem; font-size: clamp(2rem, 5vw, 3.5rem); line-height: 1.05; }
header p { max-width: 760px; color: #dbe7ff; font-size: 1.05rem; }
nav { display: flex; flex-wrap: wrap; gap: .7rem; margin-top: 1.5rem; }
nav a { padding: .65rem .9rem; border: 1px solid #7185ad; border-radius: .65rem; color: white; text-decoration: none; }
nav a:hover { background: #ffffff18; }
main { width: min(1180px, calc(100% - 2rem)); margin: 2rem auto 5rem; }
section { margin: 1.2rem 0; padding: clamp(1.2rem, 3vw, 2.2rem); border: 1px solid #dbe2ee; border-radius: 1rem; background: white; box-shadow: 0 10px 30px #23304a0b; }
h2 { margin-top: 0; color: #14213d; }
h3 { color: #263b67; }
.hipoteses { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem; }
.hipotese { padding: 1rem; border-left: 4px solid #506995; border-radius: .4rem; background: #f6f8fc; }
.grafico { min-height: 450px; }
.leitura { margin: 1.2rem 0 0; padding: 1rem 1.2rem; border-radius: .7rem; background: #f1f5fb; line-height: 1.65; }
.pendente { padding: 1.3rem; border: 1px dashed #9aa8bd; border-radius: .7rem; color: #526078; background: #fafbfc; }
.selo { display: inline-block; margin-right: .5rem; padding: .2rem .55rem; border-radius: 999px; color: #6f3d00; background: #fff0c2; font-size: .82rem; font-weight: 700; text-transform: uppercase; }
.tabela { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: .95rem; }
th, td { padding: .6rem .7rem; border-bottom: 1px solid #dbe2ee; text-align: left; vertical-align: top; }
th { color: #263b67; background: #f6f8fc; }
td.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
footer { padding: 2rem; color: #64748b; text-align: center; }
@media (max-width: 600px) { section { padding: 1rem; } .grafico { min-height: 390px; } }
</style>
</head>
<body>
<header>
  <h1>t de Welch × Mann-Whitney no tempo até o merge</h1>
  <p>Lab04 — uma comparação dos testes em dados reais de pull requests e em cenários simulados com efeito conhecido.</p>
  <nav aria-label="Links do projeto">
    <a href="$dashboard">Dashboard publicado</a>
    <a href="$repositorio">Repositório</a>
    <a href="$board">GitHub Projects</a>
  </nav>
</header>
<main>
  <section id="pergunta">
    <h2>1. Pergunta e hipóteses</h2>
    <p>O tempo até o merge de um PR no <code>langflow-ai/langflow</code> muda quando o PR recebe review do <code>coderabbitai[bot]</code>?</p>
    <div class="hipoteses">
      <div class="hipotese"><strong>t de Welch</strong><br>H₀: os tempos médios são iguais.<br>H₁: os tempos médios são diferentes.</div>
      <div class="hipotese"><strong>Mann-Whitney</strong><br>H₀: nenhum grupo tende a ter tempos maiores.<br>H₁: um grupo tende a ter tempos maiores.</div>
    </div>
    <p class="pendente"><span class="selo">entrega final</span>A origem dos dados e o fechamento desta apresentação serão detalhados na entrega final.</p>
  </section>

  <section id="g1">
    <h2>2. G1 — Tempos reais e simulados</h2>
    <div class="grafico">$g1</div>
    <p class="leitura">$texto_g1</p>
  </section>

  <section id="g2">
    <h2>3. G2 — Distribuições das estatísticas sob H₀</h2>
    <div class="grafico">$g2</div>
    <p class="leitura">$texto_g2</p>
  </section>

  <section id="g3">
    <h2>4. G3 — Erro tipo I</h2>
    <div class="grafico">$g3</div>
    <p class="leitura">$texto_g3</p>
  </section>

  <section id="g4">
    <h2>5. G4 — Poder dos testes</h2>
    <div class="grafico">$g4</div>
    <p class="leitura">$texto_g4</p>
  </section>

  <section id="dados-reais">
    <h2>6. Os dois testes nos dados reais</h2>
    $dados_reais
  </section>

  <section id="conclusao">
    <h2>7. Palpite, resultados e conclusão</h2>
    <p class="pendente"><span class="selo">entrega final</span>O confronto entre o palpite inicial e os resultados será incluído na entrega final.</p>
  </section>
</main>
<footer>Laboratório de Experimentação de Software — PUC Minas</footer>
</body>
</html>
""")


def _dados(csv: Path) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, dict]:
    reais = pd.read_csv(csv)
    p = parametros.calcular(csv)
    cenario = cenario_base(p)
    com, sem = gerar_amostra(
        np.random.default_rng(SEMENTE),
        cenario.n,
        cenario.mu,
        cenario.sigma,
        efeito_observado(p),
    )
    return reais, com[0], sem[0], p


def _histograma_em_log(valores: np.ndarray, limites: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    contagens, _ = np.histogram(valores, bins=limites)
    centros = np.sqrt(limites[:-1] * limites[1:])
    percentuais = 100 * contagens / contagens.sum()
    return centros, percentuais, np.column_stack((limites[:-1], limites[1:]))


def _figura_g1(reais: pd.DataFrame, com: np.ndarray, sem: np.ndarray) -> str:
    series = {
        "Real": {
            grupo: reais.loc[reais["grupo"] == grupo, "horas_ate_merge"].to_numpy(float)
            for grupo in GRUPOS
        },
        "Simulado": {"com_bot": com, "sem_bot": sem},
    }
    todos = np.concatenate([valores for painel in series.values() for valores in painel.values()])
    inicio = math.floor(math.log10(todos.min()))
    fim = math.ceil(math.log10(todos.max()))
    limites = np.logspace(inicio, fim, 18)
    figura = make_subplots(rows=1, cols=2, subplot_titles=("Dados reais", "Dados simulados"))

    for coluna, (painel, grupos) in enumerate(series.items(), start=1):
        for grupo, valores in grupos.items():
            centros, percentuais, intervalos = _histograma_em_log(valores, limites)
            estilo = GRUPOS[grupo]
            figura.add_trace(
                go.Bar(
                    x=centros,
                    y=percentuais,
                    width=np.diff(limites) * 0.8,
                    customdata=intervalos,
                    name=estilo["nome"],
                    legendgroup=grupo,
                    showlegend=coluna == 1,
                    marker_color=estilo["cor"],
                    opacity=0.78,
                    hovertemplate=(
                        "%{customdata[0]:.2f}–%{customdata[1]:.2f} h<br>"
                        "%{y:.1f}% dos PRs<extra>%{fullData.name}</extra>"
                    ),
                ),
                row=1,
                col=coluna,
            )

    figura.update_xaxes(type="log", title_text="Tempo até o merge (horas, escala log)")
    figura.update_yaxes(title_text="PRs no intervalo (%)", rangemode="tozero")
    figura.update_layout(
        title="Histograma do tempo até o merge por grupo",
        barmode="group",
        template="plotly_white",
        legend_title_text="Grupo",
        hovermode="closest",
        margin=dict(l=55, r=25, t=90, b=60),
    )
    return figura.to_html(
        full_html=False,
        include_plotlyjs=True,
        div_id="grafico-g1",
        config={"responsive": True, "displaylogo": False},
    )


def _graus_liberdade_welch(x: np.ndarray, y: np.ndarray) -> float:
    vx, vy = np.var(x, ddof=1) / len(x), np.var(y, ddof=1) / len(y)
    return float((vx + vy) ** 2 / (vx**2 / (len(x) - 1) + vy**2 / (len(y) - 1)))


def resumo_g2(com: np.ndarray, sem: np.ndarray) -> dict[str, float]:
    """Valores do exemplo usados para desenhar e conferir as áreas do G2."""
    resultado_w = welch(com, sem)
    resultado_m = mann_whitney(com, sem)
    n_com, n_sem = len(com), len(sem)
    media_u = n_com * n_sem / 2
    desvio_u = math.sqrt(n_com * n_sem * (n_com + n_sem + 1) / 12)
    u = float(resultado_m.estatistica)
    # A mesma correção de continuidade usada pelo scipy no teste assintótico bicaudal.
    z_u = (abs(u - media_u) - 0.5) / desvio_u
    return {
        "t": float(resultado_w.estatistica),
        "p_welch": float(resultado_w.p),
        "gl_welch": _graus_liberdade_welch(com, sem),
        "u": u,
        "media_u": media_u,
        "desvio_u": desvio_u,
        "p_mann_whitney": float(resultado_m.p),
        "z_u": z_u,
    }


def _area(
    figura: go.Figure,
    x: np.ndarray,
    y: np.ndarray,
    nome: str,
    cor: str,
    coluna: int,
    grupo_legenda: str,
    opacidade: float,
    mostrar_legenda: bool,
) -> None:
    figura.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines",
            line=dict(width=0, color=cor),
            fill="tozeroy",
            fillcolor=cor,
            opacity=opacidade,
            name=nome,
            legendgroup=grupo_legenda,
            showlegend=mostrar_legenda,
            hoverinfo="skip",
        ),
        row=1,
        col=coluna,
    )


def _duas_caudas(
    figura: go.Figure,
    x: np.ndarray,
    y: np.ndarray,
    corte: float,
    nome: str,
    cor: str,
    coluna: int,
    grupo_legenda: str,
    opacidade: float,
) -> None:
    esquerda, direita = x <= -abs(corte), x >= abs(corte)
    _area(figura, x[esquerda], y[esquerda], nome, cor, coluna, grupo_legenda, opacidade, True)
    _area(figura, x[direita], y[direita], nome, cor, coluna, grupo_legenda, opacidade, False)


def _figura_g2(resumo: dict[str, float]) -> str:
    figura = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            f"{TESTES['welch']['nome']} (gl = {resumo['gl_welch']:.1f})",
            f"{TESTES['mann_whitney']['nome']} (aproximação normal de U)",
        ),
    )

    cor_w = TESTES["welch"]["cor"]
    x_t = np.linspace(-4.5, 4.5, 900)
    y_t = stats.t.pdf(x_t, resumo["gl_welch"])
    critico_t = float(stats.t.ppf(1 - ALFA / 2, resumo["gl_welch"]))
    _duas_caudas(figura, x_t, y_t, critico_t, "Região de rejeição (α = 0,05)", cor_w, 1, "welch-rejeicao", 0.14)
    _duas_caudas(
        figura,
        x_t,
        y_t,
        abs(resumo["t"]),
        f"Área do p-valor = {resumo['p_welch']:.4f}",
        cor_w,
        1,
        "welch-p",
        0.34,
    )
    figura.add_trace(
        go.Scatter(x=x_t, y=y_t, mode="lines", name=TESTES["welch"]["nome"], line=dict(color=cor_w, width=3)),
        row=1,
        col=1,
    )

    cor_m = TESTES["mann_whitney"]["cor"]
    media, desvio = resumo["media_u"], resumo["desvio_u"]
    x_u = np.linspace(media - 4.5 * desvio, media + 4.5 * desvio, 900)
    y_u = stats.norm.pdf(x_u, loc=media, scale=desvio)
    critico_z = float(stats.norm.ppf(1 - ALFA / 2))
    critico_u = critico_z * desvio
    observado_u = resumo["z_u"] * desvio
    x_centrado = x_u - media
    _duas_caudas(figura, x_centrado, y_u, critico_u, "Região de rejeição (α = 0,05)", cor_m, 2, "mw-rejeicao", 0.14)
    _duas_caudas(
        figura,
        x_centrado,
        y_u,
        observado_u,
        f"Área do p-valor = {resumo['p_mann_whitney']:.4f}",
        cor_m,
        2,
        "mw-p",
        0.34,
    )
    # As áreas foram calculadas ao redor de zero; no painel elas voltam para a escala de U.
    for trace in figura.data:
        if trace.legendgroup in {"mw-rejeicao", "mw-p"}:
            trace.x = np.asarray(trace.x) + media
    figura.add_trace(
        go.Scatter(x=x_u, y=y_u, mode="lines", name=TESTES["mann_whitney"]["nome"], line=dict(color=cor_m, width=3)),
        row=1,
        col=2,
    )

    figura.add_vline(x=resumo["t"], line_dash="dash", line_color=cor_w, annotation_text=f"t = {resumo['t']:.3f}", row=1, col=1)
    figura.add_vline(x=resumo["u"], line_dash="dash", line_color=cor_m, annotation_text=f"U = {resumo['u']:.0f}", row=1, col=2)
    figura.update_xaxes(title_text="Estatística t", row=1, col=1)
    figura.update_xaxes(title_text="Estatística U", row=1, col=2)
    figura.update_yaxes(title_text="Densidade de probabilidade", rangemode="tozero")
    figura.update_layout(
        title="Distribuição teórica sob H₀ e áreas bicaudais do exemplo",
        template="plotly_white",
        legend_title_text="Teste e área",
        hovermode="closest",
        margin=dict(l=55, r=25, t=90, b=60),
    )
    return figura.to_html(
        full_html=False,
        include_plotlyjs=False,
        div_id="grafico-g2",
        config={"responsive": True, "displaylogo": False},
    )


def _ler_simulacoes(caminho: Path) -> pd.DataFrame:
    dados = motor.ler(caminho)
    colunas = {"situacao", "efeito", "teste", "alfa", "rejeicoes", "n_rep"}
    faltantes = colunas.difference(dados.columns)
    if faltantes:
        raise ValueError(f"{caminho} não contém as colunas: {', '.join(sorted(faltantes))}")
    if dados.empty:
        raise ValueError(f"{caminho} não contém resultados de simulação")
    if dados.duplicated(["situacao", "efeito", "teste", "alfa"]).any():
        raise ValueError(f"{caminho} contém combinações de simulação duplicadas")
    if (dados["n_rep"] <= 0).any() or (dados["rejeicoes"] < 0).any() or (
        dados["rejeicoes"] > dados["n_rep"]
    ).any():
        raise ValueError(f"{caminho} contém contagens de simulação inválidas")

    dados = dados.assign(proporcao=dados["rejeicoes"] / dados["n_rep"])
    for situacao in SITUACOES:
        recorte = dados[dados["situacao"] == situacao]
        for alfa in ALFAS:
            por_efeito = recorte[recorte["alfa"] == alfa].pivot(
                index="efeito", columns="teste", values="proporcao"
            )
            if set(por_efeito.columns) != set(TESTES) or por_efeito.isna().any().any():
                raise ValueError(
                    f"{caminho} não tem resultados pareados de Welch e Mann-Whitney "
                    f"para {situacao}, α = {alfa:g}"
                )
            if not (recorte["efeito"] == 0).any():
                raise ValueError(f"{caminho} não tem o efeito zero para {situacao}")
    return dados


def _linha_zero(dados: pd.DataFrame, situacao: str, teste: str, alfa: float) -> pd.Series:
    linha = dados[
        (dados["situacao"] == situacao)
        & (dados["efeito"] == 0)
        & (dados["teste"] == teste)
        & (dados["alfa"] == alfa)
    ]
    if linha.empty:
        raise ValueError(f"Falta o efeito zero de {teste} em {situacao}, α = {alfa:g}")
    return linha.iloc[0]


def _classificar_taxa(linha: pd.Series, alfa: float) -> str:
    tolerancia = MARGEM_G3[alfa]
    if linha["proporcao"] > alfa + tolerancia:
        return "liberal"
    if linha["proporcao"] < alfa - tolerancia:
        return "conservador"
    return "na faixa de ruído"


def _percentual(valor: float) -> str:
    return f"{100 * valor:.2f}".replace(".", ",") + "%"


def _figura_g3(dados: pd.DataFrame) -> str:
    figura = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("α = 5%", "α = 1%"),
        shared_yaxes=False,
    )
    situacoes = list(SITUACOES)
    rotulos = [SITUACOES[situacao] for situacao in situacoes]

    for coluna, alfa in enumerate(ALFAS, start=1):
        margem_pp = 100 * MARGEM_G3[alfa]
        referencia = 100 * alfa
        figura.add_hrect(
            y0=referencia - margem_pp,
            y1=referencia + margem_pp,
            fillcolor="#64748b",
            opacity=0.14,
            line_width=0,
            row=1,
            col=coluna,
        )
        figura.add_hline(
            y=referencia,
            line_dash="dash",
            line_color="#334155",
            line_width=2,
            row=1,
            col=coluna,
        )
        for teste, estilo in TESTES.items():
            linhas = [_linha_zero(dados, situacao, teste, alfa) for situacao in situacoes]
            figura.add_trace(
                go.Scatter(
                    x=rotulos,
                    y=[100 * linha["proporcao"] for linha in linhas],
                    customdata=[
                        [int(linha["rejeicoes"]), int(linha["n_rep"])] for linha in linhas
                    ],
                    mode="lines+markers",
                    name=estilo["nome"],
                    legendgroup=teste,
                    showlegend=coluna == 1,
                    line=dict(color=estilo["cor"], width=3),
                    marker=dict(size=9),
                    hovertemplate=(
                        "%{x}<br>Taxa: %{y:.2f}%<br>"
                        "Rejeições: %{customdata[0]} de %{customdata[1]}"
                        "<extra>%{fullData.name}</extra>"
                    ),
                ),
                row=1,
                col=coluna,
            )
        figura.update_xaxes(
            title_text="Situação (efeito zero)",
            tickangle=-25,
            categoryorder="array",
            categoryarray=rotulos,
            row=1,
            col=coluna,
        )
        maior_taxa = max(
            100 * dados.loc[
                (dados["situacao"].isin(situacoes)) & (dados["alfa"] == alfa)
                & (dados["efeito"] == 0),
                "proporcao",
            ].max(),
            referencia + margem_pp,
        )
        figura.update_yaxes(
            title_text="Taxa de rejeição (%)",
            range=[0, max(referencia + 2 * margem_pp, maior_taxa * 1.2)],
            row=1,
            col=coluna,
        )

    figura.update_layout(
        title="Erro tipo I: taxa de rejeição no efeito zero",
        template="plotly_white",
        legend_title_text="Teste",
        height=520,
        margin=dict(l=60, r=25, t=90, b=135),
    )
    return figura.to_html(
        full_html=False,
        include_plotlyjs=False,
        div_id="grafico-g3",
        config={"responsive": True, "displaylogo": False},
    )


def _figura_g4(dados: pd.DataFrame) -> str:
    figura = go.Figure()
    descritores = []
    for situacao in SITUACOES:
        for alfa in ALFAS:
            for teste in TESTES:
                linhas = dados[
                    (dados["situacao"] == situacao)
                    & (dados["alfa"] == alfa)
                    & (dados["teste"] == teste)
                ].sort_values("efeito")
                figura.add_trace(
                    go.Scatter(
                        x=np.exp(linhas["efeito"].to_numpy(float)),
                        y=100 * linhas["proporcao"].to_numpy(float),
                        customdata=np.column_stack((linhas["rejeicoes"], linhas["n_rep"])),
                        mode="lines+markers",
                        name=TESTES[teste]["nome"],
                        legendgroup=teste,
                        showlegend=situacao == "base" and alfa == 0.05,
                        visible=situacao == "base" and alfa == 0.05,
                        line=dict(color=TESTES[teste]["cor"], width=3),
                        marker=dict(size=7),
                        hovertemplate=(
                            "Mediana: ×%{x:.2g}<br>Poder: %{y:.1f}%<br>"
                            "Rejeições: %{customdata[0]:.0f} de %{customdata[1]:.0f}"
                            "<extra>%{fullData.name}</extra>"
                        ),
                    )
                )
                descritores.append((situacao, alfa))

    botoes = []
    for situacao, rotulo in SITUACOES.items():
        for alfa in ALFAS:
            mascara = [
                nome_situacao == situacao and nome_alfa == alfa
                for nome_situacao, nome_alfa in descritores
            ]
            botoes.append(
                {
                    "label": f"{rotulo} · α = {100 * alfa:g}%",
                    "method": "update",
                    "args": [
                        {"visible": mascara},
                        {"title": {"text": f"Poder × tamanho do efeito — {rotulo}"}},
                    ],
                }
            )

    figura.add_hline(
        y=80,
        line_dash="dash",
        line_color="#64748b",
        annotation_text="Poder de 80%",
        annotation_position="bottom right",
    )
    figura.update_xaxes(
        title_text="Multiplicador da mediana com bot (×)",
        type="log",
        tickvals=[0.4, 1, 2, 5, 10, 20, 50, 100],
        ticktext=["×0,4", "×1", "×2", "×5", "×10", "×20", "×50", "×100"],
    )
    figura.update_yaxes(title_text="Poder estimado (%)", range=[0, 100])
    figura.update_layout(
        title="Poder × tamanho do efeito — Cenário base",
        template="plotly_white",
        legend_title_text="Teste",
        updatemenus=[
            {
                "type": "dropdown",
                "direction": "down",
                "x": 0,
                "xanchor": "left",
                "y": 1.17,
                "yanchor": "top",
                "buttons": botoes,
            }
        ],
        margin=dict(l=65, r=30, t=125, b=65),
    )
    return figura.to_html(
        full_html=False,
        include_plotlyjs=False,
        div_id="grafico-g4",
        config={"responsive": True, "displaylogo": False},
    )


def _textos(reais: pd.DataFrame, com: np.ndarray, sem: np.ndarray, resumo: dict[str, float]) -> tuple[str, str]:
    medianas_reais = reais.groupby("grupo")["horas_ate_merge"].median()
    texto_g1 = (
        f"Nos dados reais, a mediana é {medianas_reais['com_bot']:.1f} h com o CodeRabbit e "
        f"{medianas_reais['sem_bot']:.1f} h sem bot; a escala log deixa visíveis tanto os merges rápidos quanto a cauda de semanas. "
        f"A amostra simulada preserva a cauda longa e o deslocamento entre os grupos, com medianas de {np.median(com):.1f} h e {np.median(sem):.1f} h. "
        "Ela não reproduz a bimodalidade dos dados reais, portanto a lognormal é uma aproximação útil, mas incompleta."
    )
    decisao_w = "não rejeita" if resumo["p_welch"] >= ALFA else "rejeita"
    decisao_m = "não rejeita" if resumo["p_mann_whitney"] >= ALFA else "rejeita"
    texto_g2 = (
        f"As áreas escuras são exatamente os p-valores bicaudais do mesmo conjunto simulado: {resumo['p_welch']:.4f} para Welch e "
        f"{resumo['p_mann_whitney']:.4f} para Mann-Whitney. "
        f"A 5%, Welch {decisao_w} H₀, enquanto Mann-Whitney {decisao_m} H₀ porque sua estatística cai na região crítica. "
        "Neste exemplo com efeito conhecido, a cauda longa reduz o sinal do teste de médias, mas afeta menos o teste baseado em postos."
    )
    return texto_g1, texto_g2


def _texto_g3(dados: pd.DataFrame) -> str:
    base_w_05 = _linha_zero(dados, "base", "welch", 0.05)
    base_m_05 = _linha_zero(dados, "base", "mann_whitney", 0.05)
    base_w_01 = _linha_zero(dados, "base", "welch", 0.01)
    base_m_01 = _linha_zero(dados, "base", "mann_whitney", 0.01)
    return (
        f"No cenário base, a 5%, Welch rejeita {_percentual(base_w_05['proporcao'])} das vezes "
        f"({_classificar_taxa(base_w_05, 0.05)}) e Mann-Whitney {_percentual(base_m_05['proporcao'])} "
        f"({_classificar_taxa(base_m_05, 0.05)}), comparados com a faixa de ruído de ±0,4 p.p. "
        "para 5% e ±0,2 p.p. para 1%. "
        f"A 1%, as taxas são {_percentual(base_w_01['proporcao'])} para Welch "
        f"({_classificar_taxa(base_w_01, 0.01)}) e {_percentual(base_m_01['proporcao'])} para Mann-Whitney "
        f"({_classificar_taxa(base_m_01, 0.01)}). "
        "Em dispersões, o efeito zero iguala as medianas, mas não as médias: a hipótese nula do Welch "
        "é falsa, então sua taxa não é erro tipo I; a do Mann-Whitney é verdadeira."
    )


def _texto_g4(dados: pd.DataFrame) -> str:
    cruzamentos = {}
    for situacao, rotulo in SITUACOES.items():
        recorte = dados[dados["situacao"] == situacao]
        efeito = q2.cruzamento(recorte, "mann_whitney", alfa=0.05)
        cruzamentos[rotulo] = "não chega" if efeito is None else f"×{math.exp(efeito):.1f}".replace(".", ",")

    cruzamentos_texto = ", ".join(
        f"{rotulo}: {efeito}" for rotulo, efeito in cruzamentos.items()
    )
    comparacoes = []
    for situacao in SITUACOES:
        for alfa in ALFAS:
            recorte = dados[(dados["situacao"] == situacao) & (dados["alfa"] == alfa)]
            por_efeito = recorte.pivot(index="efeito", columns="teste", values="proporcao")
            comparacoes.extend((por_efeito["mann_whitney"] > por_efeito["welch"]).tolist())
    if all(comparacoes):
        vantagem = (
            "Mann-Whitney tem maior poder em todos os efeitos comparáveis, nas cinco situações e "
            "nos dois α; a vantagem não muda de lado no intervalo testado."
        )
    else:
        vantagem = (
            "As curvas permitem localizar onde a vantagem de poder troca de teste; a comparação "
            "usa os mesmos efeitos simulados para ambos."
        )
    return (
        f"{vantagem} "
        f"A 5%, Mann-Whitney chega a 80% de poder nos seguintes multiplicadores: {cruzamentos_texto}; "
        "Welch não alcança 80% nem no maior efeito simulado, ×100."
    )


def _num(valor: float, casas: int) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _leitura_poder(t: testes_reais.Teste) -> str:
    nome, poder = TESTES[t.teste]["nome"], _num(100 * t.poder[ALFA], 1) + "%"
    if t.rejeita(ALFA) and t.poder[ALFA] < 0.5:
        return (
            f"O {nome} rejeitou mesmo com só {poder} de poder nesse efeito. Com poder baixo, quem passa do "
            "corte costuma ser a amostra que exagerou a diferença, então ele reforça a conclusão, mas pesa menos."
        )
    if not t.rejeita(ALFA) and t.poder[ALFA] < 0.8:
        return f"O {nome} não rejeitou, mas tinha só {poder} de poder nesse efeito: o resultado dele é inconclusivo."
    if not t.rejeita(ALFA):
        return f"O {nome} não rejeitou com {poder} de poder: um efeito desse tamanho provavelmente teria aparecido."
    return f"O {nome} tinha {poder} de poder nesse efeito, então a rejeição era o resultado esperado."


def _secao_dados_reais(r: testes_reais.Reais) -> str:
    linhas = "".join(
        f"<tr><td>{TESTES[t.teste]['nome']}</td><td class=\"num\">{testes_reais.estatistica(t).replace('.', ',')}</td>"
        f"<td class=\"num\">{_num(t.p, 4)}</td><td class=\"num\">{t.efeito_nome} = {_num(t.efeito, 3)}</td>"
        f"<td>{testes_reais.conclusao(t)}</td>"
        + "".join(f"<td class=\"num\">{_num(100 * t.poder[a], 1)}%</td>" for a in testes_reais.ALFAS)
        + "</tr>"
        for t in r.testes
    )
    w, m = r.testes
    sentido = "mais" if r.diferenca_medianas > 0 else "menos"
    if w.rejeita(ALFA) and m.rejeita(ALFA):
        decisao = f"A 5%, os dois testes rejeitam H₀: os PRs com review do bot demoram {sentido} até o merge."
    elif w.rejeita(ALFA) or m.rejeita(ALFA):
        so = w if w.rejeita(ALFA) else m
        decisao = f"A 5%, só o {TESTES[so.teste]['nome']} rejeita H₀, e os testes discordam."
    else:
        decisao = "A 5%, nenhum dos dois testes rejeita H₀."
    if w.rejeita(0.01) != m.rejeita(0.01):
        so = w if w.rejeita(0.01) else m
        outro = m if so is w else w
        decisao += (
            f" A 1% eles se separam: só o {TESTES[so.teste]['nome']} rejeita (p = {_num(so.p, 4)}), "
            f"e o {TESTES[outro.teste]['nome']} fica em p = {_num(outro.p, 4)}."
        )
    pares = 100 * (1 + m.efeito) / 2
    texto = " ".join([
        f"A mediana até o merge é {_num(r.mediana['com_bot'], 1)} h com o CodeRabbit e "
        f"{_num(r.mediana['sem_bot'], 1)} h sem bot, {_num(abs(r.diferenca_medianas), 1)} h de diferença "
        f"(cerca de {_num(abs(r.diferenca_medianas) / 24, 1)} dia).",
        decisao,
        f"O δ de Cliff de {_num(m.efeito, 2)} quer dizer que, sorteando um PR de cada grupo, o com bot demora "
        f"mais em {_num(pares, 0)}% dos pares.",
        _leitura_poder(w),
        _leitura_poder(m),
        "O bot não foi sorteado entre os PRs, então isso mostra associação, não que o CodeRabbit causa a diferença.",
    ])
    return (
        f"<p>{r.n['com_bot']} PRs com review do CodeRabbit e {r.n['sem_bot']} sem, tempo em horas brutas. "
        f"O poder é o da Q2 no efeito observado (mediana ×{_num(math.exp(r.efeito_log), 2)}), com o mesmo n.</p>\n"
        "    <div class=\"tabela\"><table>\n"
        "      <thead><tr><th>Teste</th><th>Estatística</th><th>p-valor</th><th>Tamanho de efeito</th>"
        "<th>Conclusão</th><th>Poder, α = 5%</th><th>Poder, α = 1%</th></tr></thead>\n"
        f"      <tbody>{linhas}</tbody>\n"
        "    </table></div>\n"
        f"    <p class=\"leitura\">{texto}</p>"
    )


def gerar(
    destino: Path = DESTINO,
    csv: Path = parametros.CSV,
    simulacoes: Path = motor.SAIDA,
) -> Path:
    reais, com, sem, _ = _dados(csv)
    dados_simulacoes = _ler_simulacoes(simulacoes)
    resumo = resumo_g2(com, sem)
    texto_g1, texto_g2 = _textos(reais, com, sem, resumo)
    html = MODELO.substitute(
        dashboard=DASHBOARD,
        repositorio=REPOSITORIO,
        board=BOARD,
        g1=_figura_g1(reais, com, sem),
        g2=_figura_g2(resumo),
        texto_g1=texto_g1,
        texto_g2=texto_g2,
        g3=_figura_g3(dados_simulacoes),
        g4=_figura_g4(dados_simulacoes),
        texto_g3=_texto_g3(dados_simulacoes),
        texto_g4=_texto_g4(dados_simulacoes),
        dados_reais=_secao_dados_reais(testes_reais.rodar(csv, simulacoes)),
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino

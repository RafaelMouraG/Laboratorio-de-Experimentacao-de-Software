"""Monta o dashboard do Lab04 como um único HTML que abre sem servidor."""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path
from string import Template

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

from lab04.data import coleta_prs as coleta
from lab04.simulacao import motor, parametros, pressupostos_n, q2, q3, q4
from lab04.simulacao import reais as testes_reais
from lab04.simulacao.exemplo import SEMENTE
from lab04.simulacao.gerador import cenario_base, efeito_observado, gerar as gerar_amostra
from lab04.simulacao.testes import mann_whitney, welch

REPOSITORIO = "https://github.com/RafaelMouraG/Laboratorio-de-Experimentacao-de-Software"
BOARD = "https://github.com/users/RafaelMouraG/projects/12"
# Publicado pelo .github/workflows/dashboard.yml a cada push na main.
DASHBOARD = "https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/"
DESTINO = Path(__file__).with_name("index.html")
# Da execução da coleta (#143), registrada no README: o CSV guarda só os PRs sorteados.
COLETADO_EM = "04/11/2026"
ELEGIVEIS = {"com_bot": 490, "sem_bot": 371}
DIAS_POR_MES = 365.25 / 12

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
# Cores das situações no A2, longe do azul e do vermelho dos testes.
CORES_SITUACOES = {"base": "#334155", "assimetria": "#d97706", "outliers": "#0891b2"}

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
td.certo { color: #166534; font-weight: 600; }
td.errado { color: #b91c1c; font-weight: 600; }
td.parcial { color: #92400e; font-weight: 600; }
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
    $pergunta
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
    $conclusao
  </section>

  <section id="apendice">
    <h2>Apêndice — Tamanho da amostra</h2>
    $apendice
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


def _horas(valor: float) -> str:
    return _num(valor, 1) + " h"


def _textos(reais: pd.DataFrame, com: np.ndarray, sem: np.ndarray, resumo: dict[str, float]) -> tuple[str, str]:
    horas = reais.groupby("grupo")["horas_ate_merge"]
    medianas, maximos = horas.median(), horas.max()
    semana = 7 * 24
    if maximos["com_bot"] > semana >= maximos["sem_bot"]:
        cauda = "e só o grupo com bot tem PRs que passam de uma semana"
    else:
        cauda = "e os dois grupos têm PRs que levam dias"
    texto_g1 = (
        f"A mediana real é {_horas(medianas['com_bot'])} com o CodeRabbit e {_horas(medianas['sem_bot'])} sem bot, "
        f"{cauda}. A amostra simulada, sorteada da lognormal com o mesmo n, mantém a cauda longa e o "
        f"deslocamento entre os grupos, com medianas de {_horas(float(np.median(com)))} e {_horas(float(np.median(sem)))}. "
        "O que ela não reproduz é a bimodalidade dos dados reais, um bloco de merges em poucas horas e outro "
        "de dias: a lognormal é uma aproximação útil, mas incompleta."
    )
    rejeita_w, rejeita_m = resumo["p_welch"] < ALFA, resumo["p_mann_whitney"] < ALFA
    if rejeita_m and not rejeita_w:
        decisao = (
            "A 5%, só o U cai na região de rejeição. Como o efeito foi posto pelo gerador, o Welch comete aqui "
            "um erro tipo II: os poucos PRs muito lentos inflam o desvio padrão das horas e escondem o "
            "deslocamento, enquanto nos postos eles contam só como os mais lentos."
        )
    elif rejeita_m and rejeita_w:
        decisao = "A 5%, as duas estatísticas caem na região de rejeição e os dois testes detectam o efeito posto pelo gerador."
    else:
        decisao = "A 5%, os testes não concordam com o efeito posto pelo gerador; ver a Q2 para saber se isso é comum."
    texto_g2 = (
        "As áreas escuras são os p-valores bicaudais do conjunto simulado do G1: "
        f"{_num(resumo['p_welch'], 4)} no Welch e {_num(resumo['p_mann_whitney'], 4)} no Mann-Whitney. {decisao}"
    )
    return texto_g1, texto_g2


def _situacoes_com_h0(situacoes=SITUACOES) -> list[str]:
    """Situações em que o efeito zero é H₀ verdadeira para os dois testes."""
    return [s for s in situacoes if s != "dispersoes"]


def _texto_g3(dados: pd.DataFrame) -> str:
    base = {(t, a): _linha_zero(dados, "base", t, a) for t in TESTES for a in ALFAS}
    validas = _situacoes_com_h0()
    leituras = {
        (s, t, a): _classificar_taxa(_linha_zero(dados, s, t, a), a)
        for s in validas for t in TESTES for a in ALFAS
    }
    welch_cons = all(leituras[s, "welch", a] == "conservador" for s in validas for a in ALFAS)
    nenhum_liberal = all(v != "liberal" for v in leituras.values())
    outras_w = [_linha_zero(dados, s, "welch", 0.05)["proporcao"] for s in validas if s != "base"]
    m05 = base["mann_whitney", 0.05]
    leitura_m05 = _classificar_taxa(m05, 0.05)
    frases = [
        f"No cenário base, o Mann-Whitney rejeita {_percentual(m05['proporcao'])} a 5% e "
        f"{_percentual(base['mann_whitney', 0.01]['proporcao'])} a 1%, perto de α; contra a faixa de ruído de "
        "±0,4 p.p. (±0,2 p.p. a 1%), os 5% ficam "
        + ("dentro da faixa." if leitura_m05 == "na faixa de ruído" else
           "um pouco fora, pela correção de continuidade da aproximação normal de U e pelo sorteio.")
    ]
    if welch_cons:
        frases.append(
            f"O Welch é conservador em todas as situações: rejeita {_percentual(base['welch', 0.05]['proporcao'])} a 5% "
            f"e {_percentual(base['welch', 0.01]['proporcao'])} a 1% no base, e entre "
            f"{_percentual(min(outras_w))} e {_percentual(max(outras_w))} a 5% com assimetria, outliers ou n pequeno."
        )
    else:
        frases.append(
            f"O Welch rejeita {_percentual(base['welch', 0.05]['proporcao'])} a 5% e "
            f"{_percentual(base['welch', 0.01]['proporcao'])} a 1% no base."
        )
    if nenhum_liberal:
        frases.append("Nenhum dos dois fica liberal, então nenhum rejeita H₀ verdadeira mais do que promete.")
    disp_m = _linha_zero(dados, "dispersoes", "mann_whitney", 0.05)
    frases.append(
        "Em Dispersões* o efeito zero iguala as medianas, mas não as médias: a taxa do Welch ali não é erro "
        f"tipo I, e a do Mann-Whitney ({_percentual(disp_m['proporcao'])}) é."
    )
    return " ".join(frases)


def _poder(dados: pd.DataFrame, situacao: str, teste: str, efeito: float, alfa: float = ALFA) -> float:
    linha = dados[
        (dados["situacao"] == situacao) & (dados["teste"] == teste) & (dados["alfa"] == alfa)
        & dados["efeito"].map(lambda e: math.isclose(e, efeito, abs_tol=1e-12))
    ]
    if linha.empty:
        raise ValueError(f"Falta o efeito {efeito:.3f} de {teste} em {situacao}, α = {alfa:g}")
    return float(linha["proporcao"].iloc[0])


def _vezes(efeito: float | None) -> str:
    return "não chega" if efeito is None else f"×{_num(math.exp(efeito), 1)}"


def _texto_g4(dados: pd.DataFrame, efeito_real: float) -> str:
    cruzamentos = ", ".join(
        f"{rotulo}: {_vezes(q2.cruzamento(dados[dados['situacao'] == situacao], 'mann_whitney', alfa=ALFA))}"
        for situacao, rotulo in SITUACOES.items()
    )
    comparacoes = []
    for situacao in SITUACOES:
        for alfa in ALFAS:
            recorte = dados[(dados["situacao"] == situacao) & (dados["alfa"] == alfa)]
            por_efeito = recorte.pivot(index="efeito", columns="teste", values="proporcao")
            comparacoes.extend((por_efeito["mann_whitney"] > por_efeito["welch"]).tolist())
    if all(comparacoes):
        vantagem = (
            "O Mann-Whitney tem mais poder que o Welch em todos os efeitos, nas cinco situações e nos dois α: "
            "a vantagem não muda de lado no intervalo simulado."
        )
    else:
        vantagem = "As curvas se cruzam em algum ponto da grade: ali a vantagem de poder troca de teste."
    base_w = dados[(dados["situacao"] == "base") & (dados["teste"] == "welch") & (dados["alfa"] == ALFA)]
    return (
        f"{vantagem} No efeito dos dados reais (mediana ×{_num(math.exp(efeito_real), 2)}), com o n coletado, "
        f"ele detecta a diferença em {_num(100 * _poder(dados, 'base', 'mann_whitney', efeito_real), 1)}% das amostras, "
        f"contra {_num(100 * _poder(dados, 'base', 'welch', efeito_real), 1)}% do Welch. "
        f"A 5%, o Mann-Whitney chega a 80% de poder em {cruzamentos}; o Welch não alcança 80% nem com a mediana "
        f"×100, e no cenário base a curva dele para em {_num(100 * base_w['proporcao'].max(), 1)}%."
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


def _milhar(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def _data_br(iso: str) -> str:
    ano, mes, dia = iso.split("-")
    return f"{dia}/{mes}/{ano}"


def _secao_pergunta(reais: pd.DataFrame, dados: pd.DataFrame) -> str:
    n = reais["grupo"].value_counts()
    inicio, fim = coleta.PERIODO.split("..")
    combinacoes = dados.drop_duplicates(["situacao", "efeito"])
    conjuntos = int(combinacoes["n_rep"].sum())
    n_rep = int(combinacoes["n_rep"].iloc[0]) if combinacoes["n_rep"].nunique() == 1 else None
    por_combinacao = f", cada uma com {_milhar(n_rep)} conjuntos sorteados" if n_rep else ""
    return f"""<p>O tempo até o merge de um PR no <code>{coleta.REPOSITORIO}</code> muda quando o PR recebe review do <code>{coleta.BOT_REVISOR}</code>? Sendo X o tempo de um PR com review do bot e Y o de um PR sem, os dois testes respondem a essa pergunta de jeitos diferentes:</p>
    <div class="hipoteses">
      <div class="hipotese"><strong>t de Welch</strong> compara médias<br>H₀: E[X] = E[Y], o tempo médio é o mesmo.<br>H₁: E[X] ≠ E[Y].</div>
      <div class="hipotese"><strong>Mann-Whitney</strong> compara postos<br>H₀: P(X &gt; Y) = P(Y &gt; X), nenhum grupo tende a demorar mais.<br>H₁: P(X &gt; Y) ≠ P(Y &gt; X).</div>
    </div>
    <p>Os dois são bicaudais, porque o bot pode acelerar o merge (o autor corrige antes do revisor humano chegar) ou atrasá-lo (cada comentário é mais uma rodada de ajuste). Rodam sobre as horas brutas, a escala em que a pergunta é feita. As duas H₀ só coincidem quando os grupos têm a mesma forma e diferem por um deslocamento, que é o que o cenário base simula.</p>
    <h3>De onde vêm os dados</h3>
    <p>PRs mergeados no <code>{coleta.REPOSITORIO}</code> entre {_data_br(inicio)} e {_data_br(fim)}, coletados pela API do GitHub em {COLETADO_EM}. <strong>Com bot</strong>: o <code>{coleta.BOT_REVISOR}</code> revisou o PR antes do merge. <strong>Sem bot</strong>: nenhum bot revisou. Ficaram de fora PRs abertos por bot, sincronizações de branch e merges em menos de {coleta.MINUTOS_MINIMOS} minutos, rápidos demais para o bot ter revisado. Dos {ELEGIVEIS['com_bot']} PRs com bot e {ELEGIVEIS['sem_bot']} sem que sobraram, sorteamos {coleta.POR_GRUPO} de cada (semente {coleta.SEMENTE}).</p>
    <h3>Quantas observações</h3>
    <ul>
      <li><strong>Dados reais:</strong> {int(n.sum())} PRs, {int(n['com_bot'])} com bot e {int(n['sem_bot'])} sem, com o tempo em horas da abertura ao merge.</li>
      <li><strong>Simulação:</strong> {len(combinacoes)} combinações de situação, efeito e n{por_combinacao} de uma lognormal calibrada nos PRs reais, {_milhar(conjuntos)} conjuntos no total. Os dois testes recebem exatamente os mesmos conjuntos, e cada um é avaliado a α = 5% e 1%.</li>
    </ul>"""


def _curva_amostra(dados: pd.DataFrame, csv: Path) -> pd.DataFrame | None:
    """Poder por n da Q4, ou None se o `simulacoes.csv` ainda não tem essas linhas."""
    try:
        return q4.curva(dados, csv)
    except ValueError:
        return None


def _meses_coletados() -> float:
    inicio, fim = (date.fromisoformat(d) for d in coleta.PERIODO.split(".."))
    return ((fim - inicio).days + 1) / DIAS_POR_MES


def _prs_por_mes() -> float:
    """PRs elegíveis por mês do grupo mais raro, no ritmo do período coletado."""
    return min(ELEGIVEIS.values()) / _meses_coletados()


def _grupo_mais_raro() -> str:
    return "sem bot" if ELEGIVEIS["sem_bot"] <= ELEGIVEIS["com_bot"] else "com bot"


def _tempo_de_coleta(n: int) -> str:
    """Quanto tempo de PRs do repositório dá `n` por grupo, no ritmo do período coletado."""
    meses = n / _prs_por_mes()
    if meses < 1:
        return f"{_num(meses * DIAS_POR_MES, 0)} dias"
    return f"{_num(meses, 1)} {'mês' if round(meses, 1) < 2 else 'meses'}"


def _figura_a1(curva: pd.DataFrame, coletado: int) -> str:
    figura = go.Figure()
    for alfa, traco in zip(ALFAS, ("solid", "dash")):
        for teste, estilo in TESTES.items():
            linhas = curva[(curva["teste"] == teste) & (curva["alfa"] == alfa)].sort_values("n")
            figura.add_trace(
                go.Scatter(
                    x=linhas["n"],
                    y=100 * linhas["proporcao"],
                    customdata=np.column_stack((linhas["rejeicoes"], linhas["n_rep"])),
                    mode="lines+markers",
                    name=f"{estilo['nome']}, α = {100 * alfa:g}%",
                    line=dict(color=estilo["cor"], width=3, dash=traco),
                    marker=dict(size=6),
                    hovertemplate=(
                        "n = %{x} por grupo<br>Poder: %{y:.1f}%<br>"
                        "Rejeições: %{customdata[0]:.0f} de %{customdata[1]:.0f}"
                        "<extra>%{fullData.name}</extra>"
                    ),
                )
            )
    figura.add_hline(
        y=80, line_dash="dash", line_color="#64748b",
        annotation_text="Poder de 80%", annotation_position="top left",
    )
    # Em eixo log, formas e o range do Plotly ficam em log10, não no valor.
    figura.add_vline(
        x=math.log10(coletado), line_dash="dot", line_color="#475569",
        annotation_text=f"{coletado} coletados", annotation_position="top right",
    )
    ticks = [10, 20, 30, 50, 100, 200, 500]
    figura.update_xaxes(
        title_text="PRs por grupo (escala log)", type="log", tickvals=ticks, ticktext=[str(t) for t in ticks],
        range=[math.log10(curva["n"].min() * 0.9), math.log10(curva["n"].max() * 1.1)],
    )
    figura.update_yaxes(title_text="Poder estimado (%)", range=[0, 102])
    figura.update_layout(
        title="Poder × tamanho da amostra no efeito observado",
        template="plotly_white",
        legend_title_text="Teste e α",
        margin=dict(l=65, r=30, t=90, b=65),
    )
    return figura.to_html(
        full_html=False, include_plotlyjs=False, div_id="grafico-a1",
        config={"responsive": True, "displaylogo": False},
    )


def _bloco_a1(curva: pd.DataFrame | None, coletado: int) -> str:
    if curva is None:
        return ""
    linhas = []
    for teste, estilo in TESTES.items():
        no_coletado = curva[(curva["teste"] == teste) & (curva["alfa"] == ALFA) & (curva["n"] == coletado)]
        celulas = [
            estilo["nome"],
            _num(100 * float(no_coletado["proporcao"].iloc[0]), 1) + "%",
            *(
                "não chega" if (n := q4.n_para(curva, teste, alfa)) is None else f"{n} PRs"
                for alfa in ALFAS
            ),
        ]
        linhas.append(
            f"<tr><td>{celulas[0]}</td>" + "".join(f'<td class="num">{c}</td>' for c in celulas[1:]) + "</tr>"
        )
    n_w, n_m = q4.n_para(curva, "welch"), q4.n_para(curva, "mann_whitney")
    n_w_01 = q4.n_para(curva, "welch", 0.01)
    if n_w is not None and n_m is not None and n_w_01 is not None:
        alem = n_w_01 / _prs_por_mes() > _meses_coletados()
        leitura = (
            f"Com os {coletado} PRs coletados o Mann-Whitney está a poucos PRs dos 80%; o Welch precisaria de "
            f"cerca de {_num(n_w / n_m, 0)} vezes mais. Aumentar o efeito não tira o Welch do teto da Q2, mas aumentar "
            "o n sim, porque com mais PRs a média amostral fica mais perto de normal. No ritmo do período coletado, "
            f"o grupo mais raro ({_grupo_mais_raro()}) teve cerca de {_num(_prs_por_mes(), 0)} PRs elegíveis por mês no "
            f"<code>{coleta.REPOSITORIO}</code>: os {n_m} PRs por grupo do Mann-Whitney saem de {_tempo_de_coleta(n_m)} "
            f"de PRs, os {n_w} do Welch de {_tempo_de_coleta(n_w)} e os {n_w_01} do Welch a 1% de "
            f"{_tempo_de_coleta(n_w_01)}{', mais que o período coletado' if alem else ''}."
        )
    else:
        leitura = f"Até {max(q4.TAMANHOS)} PRs por grupo, ao menos um dos testes não chega a 80%."
    return f"""
    <h3>A1 — Poder × tamanho da amostra</h3>
    <p>Quantos PRs por grupo cada teste precisa para 80% de poder, se o efeito real for o que os dados sugerem. Mesmo cenário base, mudando só o n, igual nos dois grupos.</p>
    <div class="grafico">{_figura_a1(curva, coletado)}</div>
    <div class="tabela"><table>
      <thead><tr><th>Teste</th><th>Poder com {coletado} por grupo, α = 5%</th><th>n por grupo para 80%, α = 5%</th><th>n por grupo para 80%, α = 1%</th></tr></thead>
      <tbody>{''.join(linhas)}</tbody>
    </table></div>
    <p class="leitura">{leitura}</p>"""


def _figura_a2(vantagem: pd.DataFrame) -> str:
    figura = go.Figure()
    for situacao in pressupostos_n.SITUACOES:
        linhas = vantagem[vantagem["situacao"] == situacao].sort_values("n")
        figura.add_trace(
            go.Scatter(
                x=linhas["n"],
                y=100 * linhas["diferenca"],
                customdata=100 * np.column_stack((linhas["welch"], linhas["mann_whitney"])),
                mode="lines+markers",
                name=SITUACOES[situacao],
                line=dict(color=CORES_SITUACOES[situacao], width=3),
                marker=dict(size=8),
                hovertemplate=(
                    "n = %{x} por grupo<br>Mann-Whitney − Welch: %{y:+.1f} p.p.<br>"
                    "Welch: %{customdata[0]:.1f}% · Mann-Whitney: %{customdata[1]:.1f}%"
                    "<extra>%{fullData.name}</extra>"
                ),
            )
        )
    figura.add_hline(
        y=0, line_dash="dash", line_color="#64748b",
        annotation_text="Abaixo daqui o Welch teria mais poder", annotation_position="bottom right",
    )
    ticks = list(pressupostos_n.TAMANHOS)
    figura.update_xaxes(title_text="PRs por grupo (escala log)", type="log", tickvals=ticks, ticktext=[str(t) for t in ticks])
    figura.update_yaxes(title_text="Poder do Mann-Whitney − poder do Welch (p.p.)", range=[-10, 100])
    figura.update_layout(
        title=f"Vantagem de poder do Mann-Whitney na mediana ×{pressupostos_n.MULTIPLICADOR}, α = 5%",
        template="plotly_white",
        legend_title_text="Situação",
        margin=dict(l=65, r=30, t=90, b=65),
    )
    return figura.to_html(
        full_html=False, include_plotlyjs=False, div_id="grafico-a2",
        config={"responsive": True, "displaylogo": False},
    )


def _texto_a2(curva: pd.DataFrame, vantagem: pd.DataFrame) -> str:
    v = vantagem.set_index(["situacao", "n"])
    maior_n, menor_n = max(pressupostos_n.TAMANHOS), min(pressupostos_n.TAMANHOS)

    def pp(situacao: str, n: int, coluna: str = "diferenca") -> str:
        valor = 100 * v.loc[(situacao, n), coluna]
        return (f"{valor:+.1f}".replace(".", ",") + " p.p.") if coluna == "diferenca" else _num(valor, 1) + "%"

    if (vantagem["diferenca"] > 0).all():
        frases = [
            f"O Mann-Whitney tem mais poder que o Welch em todos os pontos, então a escolha não troca de lado "
            f"entre {menor_n} e {maior_n} PRs por grupo."
        ]
    else:
        frases = ["Em algum ponto da grade o Welch tem mais poder: ali a escolha troca de lado."]
    base = v.loc["base", "diferenca"]
    pico = int(base.idxmax())
    if pico != maior_n:
        frases.append(
            f"No cenário base a vantagem chega ao máximo em n = {pico} ({pp('base', pico)}) e encolhe em {maior_n} "
            f"({pp('base', maior_n)}), porque o Mann-Whitney encosta em 100% e o Welch, com a média amostral mais "
            f"perto de normal, começa a alcançá-lo ({pp('base', maior_n, 'welch')} de poder)."
        )
    else:
        frases.append(f"No cenário base a vantagem cresce com o n até {pp('base', maior_n)}.")
    violadas = [s for s in pressupostos_n.SITUACOES if s != "base"]
    crescem = all(v.loc[s, "diferenca"].is_monotonic_increasing for s in violadas)
    frases.append(
        f"Com assimetria e outliers ela {'só cresce' if crescem else 'oscila'}, até {pp('assimetria', maior_n)} e "
        f"{pp('outliers', maior_n)} em n = {maior_n}, com o Welch em {pp('assimetria', maior_n, 'welch')} e "
        f"{pp('outliers', maior_n, 'welch')} de poder."
    )
    zero = curva[(curva["alfa"] == ALFA) & (curva["efeito"] == 0.0) & (curva["teste"] == "welch")]
    pior = zero.loc[zero["proporcao"].idxmin()]
    frases.append(
        f"Os pressupostos pesam no erro tipo I do Welch com n pequeno ({_percentual(pior['proporcao'])} em "
        f"{SITUACOES[pior['situacao']].lower()} com n = {int(pior['n'])}) e no poder dele com n grande, quando a cauda longa e "
        "os outliers o seguram enquanto o Mann-Whitney passa de 90%."
    )
    return " ".join(frases)


def _bloco_a2(curva: pd.DataFrame) -> str:
    vantagem = pressupostos_n.vantagem(curva)
    return f"""
    <h3>A2 — O melhor teste muda com o tamanho da amostra?</h3>
    <p>Cenário base, assimetria e outliers da Q3 com {', '.join(map(str, pressupostos_n.TAMANHOS[:-1]))} e {pressupostos_n.TAMANHOS[-1]} PRs por grupo. O poder é medido na mediana ×{pressupostos_n.MULTIPLICADOR}, em que o Mann-Whitney tem cerca de metade de poder no cenário base com o n coletado; o erro tipo I, no efeito zero.</p>
    <div class="grafico">{_figura_a2(vantagem)}</div>
    <p class="leitura">{_texto_a2(curva, vantagem)}</p>"""


def _secao_apendice(
    curva: pd.DataFrame | None,
    curva_pressupostos: pd.DataFrame,
    p: dict[str, parametros.Parametros],
) -> str:
    return (
        "<p>Duas perguntas que o enunciado deixa para o fim: quantos PRs bastariam e se a escolha do teste muda com o "
        "n. Ficam fora das sete seções, que têm ordem fixa.</p>"
        + _bloco_a1(curva, p["com_bot"].n)
        + _bloco_a2(curva_pressupostos)
    )


def _secao_conclusao(
    dados: pd.DataFrame,
    p: dict[str, parametros.Parametros],
    reais: pd.DataFrame,
    curva: pd.DataFrame | None,
) -> str:
    efeito_real = efeito_observado(p)
    cinco = math.log(5)

    def zero(situacao: str, teste: str) -> str:
        return _percentual(_linha_zero(dados, situacao, teste, ALFA)["proporcao"])

    def poder(situacao: str, teste: str, efeito: float = cinco) -> str:
        return _num(100 * _poder(dados, situacao, teste, efeito), 1) + "%"

    def cruza(situacao: str) -> str:
        return _vezes(q2.cruzamento(dados[dados["situacao"] == situacao], "mann_whitney", alfa=ALFA))

    base_w = dados[(dados["situacao"] == "base") & (dados["teste"] == "welch") & (dados["alfa"] == ALFA)]
    disp = q3.situacoes(p)["dispersoes"]
    medias_iguais = q3.efeito_medias_iguais(disp)
    linhas = [
        ("Erro tipo I no cenário base",
         "Os dois perto de 5%, com o Welch um pouco abaixo (conservador).",
         f"Mann-Whitney em {zero('base', 'mann_whitney')}; Welch em {zero('base', 'welch')}, bem abaixo da faixa de ruído.",
         "parcial", "Direção certa, tamanho errado"),
        ("Poder",
         "O Mann-Whitney chega a 80% com um efeito bem menor, e a diferença é grande.",
         f"Mann-Whitney chega a 80% na mediana {cruza('base')}; o Welch não chega nem em ×100 "
         f"(para em {_num(100 * base_w['proporcao'].max(), 1)}%).",
         "certo", "Acertou, com diferença maior que a apostada"),
        ("Assimetria e outliers",
         "Aumentam a vantagem do Mann-Whitney.",
         f"Na mediana ×5, o Welch cai de {poder('base', 'welch')} para {poder('assimetria', 'welch')} com assimetria "
         f"e {poder('outliers', 'welch')} com outliers; o Mann-Whitney, de {poder('base', 'mann_whitney')} para "
         f"{poder('assimetria', 'mann_whitney')} e {poder('outliers', 'mann_whitney')}.",
         "certo", "Acertou"),
        ("n = 10 por grupo",
         "Os dois perdem poder, e o Welch fica mais conservador.",
         f"Welch rejeita {zero('n_pequeno', 'welch')} sob H₀; o Mann-Whitney só chega a 80% na mediana {cruza('n_pequeno')}.",
         "certo", "Acertou"),
        ("Mesma mediana, σ diferentes",
         "Welch bem acima de 5%, certo para a pergunta dele; Mann-Whitney um pouco fora de 5%.",
         f"Welch em {zero('dispersoes', 'welch')}, abaixo do próprio α mesmo com a H₀ dele falsa; Mann-Whitney em "
         f"{zero('dispersoes', 'mann_whitney')}, dentro da faixa.",
         "errado", "Errou"),
    ]
    tabela = "".join(
        f"<tr><td>{ponto}</td><td>{palpite}</td><td>{resultado}</td><td class=\"{classe}\">{leitura}</td></tr>"
        for ponto, palpite, resultado, classe, leitura in linhas
    )
    w_real = _poder(dados, "base", "welch", efeito_real)
    m_real = _poder(dados, "base", "mann_whitney", efeito_real)
    n_w = q4.n_para(curva, "welch") if curva is not None else None
    n_w_01 = q4.n_para(curva, "welch", 0.01) if curva is not None else None
    n_media = (
        f" Com essa cauda, porém, o Welch só chega a 80% de poder com cerca de {n_w} PRs por grupo "
        f"({n_w_01} a 1%), contra os {p['com_bot'].n} coletados (ver o apêndice)."
        if n_w is not None and n_w_01 is not None else ""
    )
    autor, fracao = _autor_dominante(reais)
    pagina_cenario = f"{REPOSITORIO}/blob/main/lab04/cenario.md"
    return f"""<h3>O palpite contra a simulação</h3>
    <p>O palpite foi escrito no <a href="{pagina_cenario}"><code>cenario.md</code></a> antes da primeira simulação, e o histórico do arquivo no git é a prova disso.</p>
    <div class="tabela"><table>
      <thead><tr><th>Ponto</th><th>Palpite</th><th>O que a simulação mostrou (α = 5%)</th><th>Leitura</th></tr></thead>
      <tbody>{tabela}</tbody>
    </table></div>
    <p class="leitura">O palpite acertou quem ganha e por quê, mas subestimou o tamanho: a cauda longa não deixa o Welch só um pouco conservador, tira dele a maior parte do poder. O erro foi em Dispersões*: a mesma cauda que cria a diferença de médias deixa o Welch sem poder para vê-la.</p>
    <h3>Qual teste usar neste cenário</h3>
    <p class="leitura"><strong>Mann-Whitney.</strong> Ele mantém o erro tipo I perto de α em todas as situações simuladas, enquanto o Welch fica conservador em todas. No efeito que os dados sugerem tem {_num(100 * m_real, 1)}% de poder contra {_num(100 * w_real, 1)}% do Welch, então, com o n coletado, um Welch não significativo seria o resultado esperado mesmo com o efeito existindo. E responde a uma pergunta útil para quem espera o merge: sorteando um PR de cada grupo, o com bot tende a demorar mais?</p>
    <h3>Quando a escolha mudaria</h3>
    <ul>
      <li><strong>Se a pergunta for sobre a média</strong>, como o total de horas de espera somado no mês, que é o que pesa no custo do time. Aí a H₀ do Welch é a pergunta certa, e o Mann-Whitney responde outra coisa.{n_media}</li>
      <li><strong>Se os grupos tiverem formas diferentes</strong>, como em Dispersões*. Aí os dois testes deixam de responder à mesma pergunta: no ponto em que as médias ficam iguais (mediana com bot ×{_num(math.exp(medias_iguais), 2)}), o Mann-Whitney rejeitou {poder('dispersoes', 'mann_whitney', medias_iguais)} e o Welch {poder('dispersoes', 'welch', medias_iguais)}. "O Mann-Whitney rejeitou e o Welch não" pode querer dizer "a mediana mudou e a média não", e quem quer falar de média precisa do Welch, com o n que ele pede.</li>
      <li><strong>Se a cauda fosse curta</strong> (σ do log bem menor que o {_num(parametros.sigma_comum(p), 1)} do cenário base), a média amostral ficaria perto de normal e os dois testes deveriam se aproximar. Essa situação fica fora da grade que simulamos.</li>
    </ul>
    <h3>Principal limitação</h3>
    <p class="leitura">A comparação dos testes vale para dados parecidos com a lognormal calibrada, e os dados reais não são tão parecidos: o log das horas é bimodal (Shapiro com p = {_num(p['com_bot'].shapiro_p, 3)} com bot e {_num(p['sem_bot'].shapiro_p, 3)} sem), e o G1 mostra que a simulação não reproduz isso. A Q3 estressou a cauda longa, os outliers e o n, mas não uma mistura de dois tipos de PR. Sobre a pergunta em si, os dados são observacionais: o bot não foi sorteado e {_num(100 * fracao, 0)}% dos PRs são do mesmo autor (<code>{autor}</code>), então a diferença no tempo até o merge mostra associação, não efeito do CodeRabbit.</p>"""


def _autor_dominante(reais: pd.DataFrame) -> tuple[str, float]:
    contagem = reais["autor"].value_counts()
    return str(contagem.index[0]), float(contagem.iloc[0] / len(reais))


def gerar(
    destino: Path = DESTINO,
    csv: Path = parametros.CSV,
    simulacoes: Path = motor.SAIDA,
    tamanho_amostra: Path = pressupostos_n.SAIDA,
) -> Path:
    reais, com, sem, p = _dados(csv)
    dados_simulacoes = _ler_simulacoes(simulacoes)
    curva = _curva_amostra(dados_simulacoes, csv)
    resultado_reais = testes_reais.rodar(csv, simulacoes)
    resumo = resumo_g2(com, sem)
    texto_g1, texto_g2 = _textos(reais, com, sem, resumo)
    html = MODELO.substitute(
        dashboard=DASHBOARD,
        repositorio=REPOSITORIO,
        board=BOARD,
        pergunta=_secao_pergunta(reais, dados_simulacoes),
        g1=_figura_g1(reais, com, sem),
        g2=_figura_g2(resumo),
        texto_g1=texto_g1,
        texto_g2=texto_g2,
        g3=_figura_g3(dados_simulacoes),
        g4=_figura_g4(dados_simulacoes),
        texto_g3=_texto_g3(dados_simulacoes),
        texto_g4=_texto_g4(dados_simulacoes, efeito_observado(p)),
        dados_reais=_secao_dados_reais(resultado_reais),
        conclusao=_secao_conclusao(dados_simulacoes, p, reais, curva),
        apendice=_secao_apendice(
            curva,
            pressupostos_n.curva(dados_simulacoes, motor.ler(tamanho_amostra), csv),
            p,
        ),
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino

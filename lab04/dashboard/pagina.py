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

from lab04.simulacao import parametros
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
    <p class="pendente"><span class="selo">S02</span>As taxas de rejeição sob H₀ serão incluídas na Sprint 02.</p>
  </section>

  <section id="g4">
    <h2>5. G4 — Poder dos testes</h2>
    <p class="pendente"><span class="selo">S02</span>As curvas de poder por tamanho de efeito serão incluídas na Sprint 02.</p>
  </section>

  <section id="dados-reais">
    <h2>6. Os dois testes nos dados reais</h2>
    <p class="pendente"><span class="selo">entrega final</span>A tabela com estatística, p-valor, tamanho de efeito e conclusão será incluída na entrega final.</p>
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


def gerar(destino: Path = DESTINO, csv: Path = parametros.CSV) -> Path:
    reais, com, sem, _ = _dados(csv)
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
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino

"""RQ 09: regra e cortes dos níveis de adoção de agentes de IA (#118).

Execute da raiz do repositório com ``python -m lab03.analise.rq09_niveis``.

Este arquivo foi commitado antes de qualquer código que cruze os níveis com as métricas DORA, como
fizemos com as hipóteses. Ele só lê o ``repos.csv``; nada aqui olha o ``metricas.csv``.

A % de cada repositório é a ``proporcao_ia_desde_adocao`` do ``repos.csv``: commits com IA dividido
pelos commits da janela a partir do primeiro commit com IA, inclusive (``metricas/agentes.py``). Os
commits depois da adoção não estão no CSV, mas saem da conta inversa,
``commits_ia / proporcao_ia_desde_adocao``, que dá um inteiro a menos de erro de ponto flutuante
(arredondamos). Com esse inteiro, os cortes são comparados em frações exatas, sem ponto flutuante.

Regras:

- **Nenhuma:** repositório sem nenhum commit com IA (``commits_ia == 0``). Ele não tem data de adoção,
  então a regra dos 10 commits não se aplica e ele sempre entra.
- **Excluído:** repositório com commit com IA e menos de ``MINIMO_COMMITS`` commits depois da adoção.
  A % dele não é confiável (1 de 3 já dá 33%), então fica fora de todas as classificações e entra no
  funil.
- **C1 (referência),** os 5 níveis de Robbes et al. (2026, seção 4.3): experimental (< 1%), limitada
  (1% a < 5%), consistente (5% a < 20%) e disseminada (>= 20%).
- **C2:** nenhuma + tercis da % entre os adotantes que entram.
- **C3:** nenhuma + quartis da % entre os adotantes que entram. Tercis e quartis saem do posto da
  %, com empates no mesmo grupo (``_quantis``).
- **C4:** nenhuma × só commits soltos × arquivo de agente versionado (``arquivo_agente``, no último
  commit da janela). Aqui o arquivo conta mesmo sem commit marcado: os 6 repositórios com arquivo e
  sem commit com IA são "nenhuma" na C1 a C3 e "arquivo" na C4. O arquivo escondido pelo
  ``.gitignore`` não conta, porque não é versionado.

Para os testes com poucos repositórios por grupo e para comparar classificações com números de
níveis diferentes, os níveis vizinhos são unidos em nenhuma / baixa / alta (``AGRUPAMENTO``):

| Classificação | baixa | alta |
|---|---|---|
| C1 | experimental, limitada (< 5%) | consistente, disseminada (>= 5%) |
| C2 | 1º tercil | 2º e 3º tercis |
| C3 | 1º e 2º quartis | 3º e 4º quartis |
| C4 | só commits soltos | arquivo versionado |

Na C2 não há como unir vizinhos de forma simétrica com três grupos; ficou o 1º tercil sozinho como
baixa, decisão nossa e sem base na literatura. Na C4 a ordem supõe que o arquivo versionado indica
adoção mais institucional que o commit solto.
"""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations
from pathlib import Path

import pandas as pd

from lab03.analise.comum import DADOS, salvar_tabela
from lab03.analise.rq07 import comparar

MINIMO_COMMITS = 10
# Cortes de Robbes et al. (2026, seção 4.3), limite inferior de cada nível, inclusive.
CORTES_C1 = ((Fraction(20, 100), 4), (Fraction(5, 100), 3), (Fraction(1, 100), 2), (Fraction(0), 1))

NENHUMA = 0
NIVEIS = {
    "C1": {0: "nenhuma", 1: "experimental", 2: "limitada", 3: "consistente", 4: "disseminada"},
    "C2": {0: "nenhuma", 1: "T1", 2: "T2", 3: "T3"},
    "C3": {0: "nenhuma", 1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"},
    "C4": {0: "nenhuma", 1: "commits soltos", 2: "arquivo versionado"},
}
CLASSIFICACOES = tuple(NIVEIS)
GRUPOS = {0: "nenhuma", 1: "baixa", 2: "alta"}
# código do nível → código do grupo (0 nenhuma, 1 baixa, 2 alta)
AGRUPAMENTO = {
    "C1": {0: 0, 1: 1, 2: 1, 3: 2, 4: 2},
    "C2": {0: 0, 1: 1, 2: 2, 3: 2},
    "C3": {0: 0, 1: 1, 2: 1, 3: 2, 4: 2},
    "C4": {0: 0, 1: 1, 2: 2},
}


def commits_desde_adocao(commits_ia: int, proporcao: float) -> int:
    """Commits da janela a partir do primeiro commit com IA, pela conta inversa da proporção."""
    if commits_ia == 0:
        return 0
    return round(commits_ia / proporcao)


def nivel_c1(commits_ia: int, desde: int) -> int:
    """Nível de Robbes et al. pela fração exata ``commits_ia / desde``."""
    if commits_ia == 0:
        return NENHUMA
    fracao = Fraction(commits_ia, desde)
    for corte, nivel in CORTES_C1:
        if fracao >= corte:
            return nivel
    raise ValueError("fração negativa")  # pragma: no cover


def nivel_c4(commits_ia: int, arquivo: bool) -> int:
    if arquivo:
        return 2
    return 1 if commits_ia > 0 else NENHUMA


def _quantis(proporcao: pd.Series, adotante: pd.Series, partes: int) -> pd.Series:
    """Nenhuma para quem não adotou e 1..``partes`` pelos quantis da % entre os adotantes.

    O grupo sai do posto: ``1 + floor(partes * (posto - 1) / n)``, com o menor posto para empates.
    Assim repositórios com a mesma % caem sempre no mesmo grupo, o que o ``pd.qcut`` não garante.
    """
    niveis = pd.Series(NENHUMA, index=proporcao.index, dtype="Int64")
    n = int(adotante.sum())
    if n:
        postos = proporcao[adotante].rank(method="min").astype(int)
        niveis[adotante] = 1 + (partes * (postos - 1)) // n
    return niveis


def classificar(repos: pd.DataFrame, minimo: int = MINIMO_COMMITS) -> pd.DataFrame:
    """Uma linha por repositório com a % e os códigos de C1 a C4; excluídos ficam com nível vazio.

    Espera as colunas ``repo``, ``commits_ia``, ``proporcao_ia_desde_adocao`` e ``arquivo_agente``.
    """
    tabela = repos[["repo", "commits_ia", "proporcao_ia_desde_adocao", "arquivo_agente"]].copy()
    tabela["commits_ia"] = tabela["commits_ia"].astype(int)
    tabela["arquivo_agente"] = tabela["arquivo_agente"].astype(bool)
    tabela["commits_desde_adocao"] = [
        commits_desde_adocao(c, p) for c, p in zip(tabela["commits_ia"], tabela["proporcao_ia_desde_adocao"])
    ]
    tabela["proporcao"] = tabela["proporcao_ia_desde_adocao"].astype(float).fillna(0.0)
    adotou = tabela["commits_ia"] > 0
    tabela["excluido"] = adotou & (tabela["commits_desde_adocao"] < minimo)
    entra = ~tabela["excluido"]
    adotante = adotou & entra

    for nome in CLASSIFICACOES:
        tabela[nome] = pd.Series(pd.NA, index=tabela.index, dtype="Int64")
    tabela.loc[entra, "C1"] = [
        nivel_c1(c, d) for c, d in zip(tabela.loc[entra, "commits_ia"], tabela.loc[entra, "commits_desde_adocao"])
    ]
    tabela.loc[entra, "C2"] = _quantis(tabela["proporcao"], adotante, 3)[entra]
    tabela.loc[entra, "C3"] = _quantis(tabela["proporcao"], adotante, 4)[entra]
    tabela.loc[entra, "C4"] = [
        nivel_c4(c, a) for c, a in zip(tabela.loc[entra, "commits_ia"], tabela.loc[entra, "arquivo_agente"])
    ]
    for nome in CLASSIFICACOES:
        tabela[f"{nome}_grupo"] = tabela[nome].map(AGRUPAMENTO[nome]).astype("Int64")
    return tabela.drop(columns="proporcao_ia_desde_adocao")


def com_rotulos(tabela: pd.DataFrame) -> pd.DataFrame:
    """Troca os códigos pelos nomes dos níveis, para gravar."""
    saida = tabela.copy()
    for nome in CLASSIFICACOES:
        saida[nome] = saida[nome].map(NIVEIS[nome])
        saida[f"{nome}_grupo"] = saida[f"{nome}_grupo"].map(GRUPOS)
    return saida


def funil(tabela: pd.DataFrame, minimo: int = MINIMO_COMMITS) -> pd.DataFrame:
    adotou = tabela["commits_ia"] > 0
    excluidos = int(tabela["excluido"].sum())
    return pd.DataFrame([
        {"etapa": "repositórios no repos.csv", "repos": len(tabela)},
        {"etapa": "sem commit com IA (nenhuma)", "repos": int((~adotou).sum())},
        {"etapa": "com pelo menos um commit com IA", "repos": int(adotou.sum())},
        {"etapa": f"excluídos: menos de {minimo} commits depois da adoção", "repos": excluidos},
        {"etapa": "adotantes classificados", "repos": int(adotou.sum()) - excluidos},
        {"etapa": "classificados no total", "repos": len(tabela) - excluidos},
    ])


def distribuicao(tabela: pd.DataFrame) -> pd.DataFrame:
    """Quantos repositórios em cada nível de cada classificação."""
    linhas = []
    for nome in CLASSIFICACOES:
        contagem = tabela[nome].value_counts()
        for codigo, rotulo in NIVEIS[nome].items():
            linhas.append({"classificacao": nome, "codigo": codigo, "nivel": rotulo,
                           "grupo": GRUPOS[AGRUPAMENTO[nome][codigo]], "repos": int(contagem.get(codigo, 0))})
    return pd.DataFrame(linhas)


def limites(tabela: pd.DataFrame) -> pd.DataFrame:
    """Menor e maior % de cada nível de adotante, para ver onde caíram os tercis e quartis."""
    linhas = []
    for nome in CLASSIFICACOES:
        adotantes = tabela[tabela[nome].notna() & (tabela[nome] != NENHUMA) & (tabela["commits_ia"] > 0)]
        for codigo, grupo in adotantes.groupby(nome)["proporcao"]:
            linhas.append({"classificacao": nome, "nivel": NIVEIS[nome][int(codigo)], "n": len(grupo),
                           "minimo": grupo.min(), "maximo": grupo.max()})
    return pd.DataFrame(linhas)


def concordancia(tabela: pd.DataFrame) -> pd.DataFrame:
    """% que muda e kappa ponderado linear entre cada par de classificações.

    Todos os pares são comparados nos três grupos (nenhuma / baixa / alta), única escala comum às
    quatro. A C1 e a C3 têm cinco níveis cada e também são comparadas nos níveis próprios. O recorte
    ``adotantes`` tira os repositórios sem commit com IA, que são "nenhuma" na C1 a C3 por construção e
    inflam a concordância.
    """
    recortes = {"todos": tabela, "adotantes": tabela[tabela["commits_ia"] > 0]}
    linhas = []
    for recorte, df in recortes.items():
        indexado = df.set_index("repo")
        for a, b in combinations(CLASSIFICACOES, 2):
            linhas.append({"recorte": recorte, "escala": "nenhuma/baixa/alta", "par": f"{a} x {b}",
                           **comparar(indexado[f"{a}_grupo"], indexado[f"{b}_grupo"], labels=list(GRUPOS))})
        linhas.append({"recorte": recorte, "escala": "níveis próprios", "par": "C1 x C3",
                       **comparar(indexado["C1"], indexado["C3"], labels=list(NIVEIS["C1"]))})
    return pd.DataFrame(linhas)


def carregar_niveis(dados: Path = DADOS) -> pd.DataFrame:
    return classificar(pd.read_csv(dados / "repos.csv"))


def main() -> int:
    tabela = carregar_niveis()
    etapas = funil(tabela)
    contagem = distribuicao(tabela)
    faixas = limites(tabela)
    pares = concordancia(tabela)

    salvar_tabela(com_rotulos(tabela), "rq09_niveis")
    salvar_tabela(etapas, "rq09_niveis_funil")
    salvar_tabela(contagem, "rq09_niveis_distribuicao")
    salvar_tabela(faixas, "rq09_niveis_limites")
    salvar_tabela(pares, "rq09_niveis_concordancia")

    print("RQ 09: níveis de adoção")
    print(etapas.to_string(index=False))
    print(contagem.to_string(index=False))
    print(faixas.to_string(index=False))
    print(pares.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

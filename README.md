# Laboratório de Experimentação de Software

## Integrantes
- Athos Marques Ribeiro Fonseca
- Mateus Araujo Santos
- Rafael Ganascini de Moura

### INFORMAÇÕES DOCENTE

| CURSO: ENGENHARIA DE SOFTWARE | DISCIPLINA: LABORATÓRIO DE EXPERIMENTAÇÃO DE SOFTWARE | TURNO: NOITE | PERÍODO/SALA: 6º |
|---|---|---|---|

**PROFESSOR(A):** Danilo Maia

---

## Laboratórios

| Lab | Tema | Pontos | Pasta |
|---|---|---|---|
| 01 | Características de repositórios populares + setup do Kanban | 15 | [`lab01/`](lab01/README.md) |
| 02 | — | — | [`lab02/`](lab02/README.md) |
| 03 | — | — | [`lab03/`](lab03/README.md) |

Cada laboratório é autocontido: enunciado, scripts (`src/`), dados coletados (`data/`) e relatório
(`relatorio/`) ficam dentro da pasta do lab.

O quadro Kanban é a exceção — ele atravessa o semestre inteiro e por isso mora em
[`kanban/`](kanban/README.md), junto com os snapshots de fechamento de cada sprint.

## Estrutura do repositório

```
README.md              este arquivo
requirements.txt       dependências de todos os labs
kanban/                board do grupo: script de snapshot e a série de CSVs por sprint
lab01/                 Lab01 — enunciado, src/ e data/
lab02/, lab03/         demais laboratórios, no mesmo padrão
```

## Links do grupo

- **Repositório:** https://github.com/RafaelMouraG/Laboratorio-de-Experimentacao-de-Software
- **GitHub Projects (v2):** https://github.com/users/RafaelMouraG/projects/6

## Convenção de commits

**Referencie o número da Issue em cada commit** (ex.: `#12 implementa consulta GraphQL`), para que
o GitHub vincule automaticamente commit ↔ Issue no histórico. **A correção do professor é feita a
partir do board:** commits sem essa referência não são considerados na avaliação, mesmo estando no
repositório.

---

## Setup do ambiente

Vale para os scripts de todos os laboratórios. **Rode sempre a partir da raiz do repositório** — os
caminhos padrão dos scripts (ex.: `lab01/data/sprint_s01/all_rqs.csv`) são relativos a ela.

### 1. Autenticação

Crie um arquivo `.env` na raiz do projeto com um Personal Access Token do GitHub:

```env
GITHUB_TOKEN=ghp_seu_token_aqui
```

O token precisa de leitura de repositórios públicos e, para o script de snapshot do Kanban, do
escopo `read:project`.

### 2. Ambiente virtual e dependências

Crie o ambiente uma vez, na raiz do projeto (`.venv/` já está no `.gitignore`, não vai pro
repositório):

```bash
python3 -m venv .venv
```

Ative o ambiente — isso precisa ser feito **em cada terminal novo**, antes de rodar qualquer script:

```bash
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows (PowerShell)
```

Com o ambiente ativo aparece `(.venv)` no início do prompt. Instale as dependências (só na primeira
vez, ou quando o `requirements.txt` mudar):

```bash
pip install -r requirements.txt
```

Confira se deu certo:

```bash
python -c "import pandas, requests, dotenv; print('ok')"
```

Para sair do ambiente, `deactivate`. Se preferir não ativar, dá pra chamar o interpretador direto:
`./.venv/bin/python lab01/src/analysis/analyze_rq07.py`.

> Os comandos da documentação usam `python`, que com o ambiente ativo é o do `.venv`. Sem ativar, o
> `python3` do sistema não enxerga o pandas e os scripts quebram com
> `ModuleNotFoundError: No module named 'pandas'`.

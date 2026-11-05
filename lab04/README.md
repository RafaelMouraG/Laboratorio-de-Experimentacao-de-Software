# Lab04: Testes de Hipótese por Dentro

Comparamos o t de Welch e o Mann-Whitney no tempo até o merge de PRs, com e sem bot de revisão. Os
dados reais calibram a simulação e, como somos nós que geramos os dados simulados, dá para medir
quantas vezes cada teste acerta ou erra.

- **Dashboard:** https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/
- **Board:** https://github.com/users/RafaelMouraG/projects/12

> Setup do ambiente (`.env`, `.venv`, dependências) está no [README da raiz](../README.md).

## Como rodar

Da raiz do repositório:

```bash
python -m lab04
```

O comando roda tudo, com semente fixa, regrava `lab04/saida/simulacoes.csv` e grava o dashboard em `lab04/dashboard/index.html`, que abre
direto no navegador. Esse HTML é gerado, por isso fica fora do git. A versão publicada é gerada pelo
workflow `.github/workflows/dashboard.yml`, com o mesmo comando, a cada push na `main`.

## Pastas

| Pasta | O que guarda |
|---|---|
| `data/` | Os PRs coletados, em CSV, e o script da coleta |
| `simulacao/` | Gerador dos dados simulados, os dois testes e o motor das repetições |
| `saida/` | `simulacoes.csv`, com as rejeições de cada teste em cada situação, efeito e α |
| `dashboard/` | Código que monta a página |
| `tests/` | Testes, com `pytest lab04/tests` |

## Dados reais

`data/prs.csv` tem 30 PRs mergeados por grupo do `langflow-ai/langflow`, de 01/08 a 31/10/2026, coletados em
04/11/2026 com `python -m lab04.data.coleta_prs` (semente 42). O repositório foi escolhido por ter PRs
suficientes com e sem o bot no mesmo período: 490 com review do CodeRabbit e 371 sem.

- **Com bot:** o `coderabbitai[bot]` revisou antes do merge.
- **Sem bot:** nenhum bot revisou o PR.
- **Fora dos dois grupos:** PRs abertos por bot, sincronização de branch (título começando com
  "Merge ") e merges em menos de 10 minutos, tempo curto demais para o CodeRabbit ter revisado.

O script fica fora do comando único: a análise lê o CSV versionado, para o resultado não depender do
que o GitHub devolve no dia.

**Limites para a conclusão.** O bot não foi sorteado entre os PRs, então a comparação não prova causa.
Uma pessoa (`erichare`) abriu a maior parte dos PRs dos dois grupos, então as observações não são
totalmente independentes. Quase todos os PRs vão para branches de release, e o tempo conta desde a
abertura do PR, incluindo o período como rascunho.

## Um conjunto simulado

Antes das 10.000 repetições, um conjunto só, com H₁ verdadeira por construção: o grupo com bot é
sorteado com o μ deslocado pela diferença entre os μ dos grupos reais. Os testes estão em
`simulacao/testes.py`, com o Mann-Whitney bicaudal e com a aproximação normal de U (o motivo está
no próprio arquivo). A tabela é gerada por `python -m lab04.simulacao.exemplo` e não deve ser
editada à mão.

<!-- exemplo:inicio -->
Semente 42, n = 30 por grupo, σ = 2.136, μ sem bot = 1.503 e efeito = 1.561 no log (tempos do grupo com bot × 4.76).

| Grupo simulado | Mediana (h) | Média (h) |
|---|---|---|
| com_bot | 26.4 | 57.5 |
| sem_bot | 6.5 | 27.6 |

| Teste | Estatística | p-valor | Tamanho de efeito |
|---|---|---|---|
| t de Welch | t = 1.513 | 0.1359 | g de Hedges = 0.385 |
| Mann-Whitney | U = 658 | 0.0022 | δ de Cliff = 0.462 |
<!-- exemplo:fim -->

O efeito existe neste conjunto, porque foi posto pelo gerador, mas só o Mann-Whitney rejeita H₀ a
5%. O Welch, com p = 0,14, comete um erro tipo II. O δ de Cliff de 0,46 quer dizer que, sorteando
um PR de cada grupo, o com bot demora mais em cerca de 73% dos pares ((1 + δ) / 2). Já o g de 0,39
sai pequeno porque poucos PRs muito lentos inflam o desvio padrão das horas brutas, e o sinal do
deslocamento se perde nesse ruído. Isso bate com o palpite do `cenario.md`, mas é um conjunto só.
Quantas vezes isso acontece é o que a Q2 mede com 10.000 repetições.

## Q1: erro tipo I

O motor (`simulacao/motor.py`) repete o gerador e os dois testes 10.000 vezes por combinação de
situação e efeito, com os mesmos dados indo para o Welch e para o Mann-Whitney. Cada combinação tem
uma semente própria, derivada da 42 e do nome da combinação, então acrescentar uma situação não
muda as que já rodaram. Tudo vai para `saida/simulacoes.csv`, em formato longo, com α = 5% e 1%.

Com 10.000 repetições, a taxa de rejeição de um teste exato fica dentro de α ± 1,96·√(α(1 − α)/10.000)
em 95% das vezes: cerca de ±0,43 ponto percentual em 5% e ±0,20 em 1%. Fora dessa faixa, o desvio é
do teste, não do sorteio. A tabela é gerada por `python -m lab04.simulacao.q1` e não deve ser
editada à mão.

<!-- q1:inicio -->
10000 repetições, cenário base com efeito zero (H₀ verdadeira para os dois testes), semente 42.

| Teste | α | Rejeições | Erro tipo I | Faixa esperada (α ± margem de 95%) | Leitura |
|---|---|---|---|---|---|
| t de Welch | 5.00% | 156 | 1.56% | 4.57% a 5.43% | abaixo da faixa |
| Mann-Whitney | 5.00% | 438 | 4.38% | 4.57% a 5.43% | abaixo da faixa |
| t de Welch | 1.00% | 7 | 0.07% | 0.80% a 1.20% | abaixo da faixa |
| Mann-Whitney | 1.00% | 84 | 0.84% | 0.80% a 1.20% | dentro da faixa |
<!-- q1:fim -->

**Welch: conservador, e muito.** Rejeita 1,6% das vezes em vez de 5%, e 0,07% em vez de 1%, bem
abaixo da faixa nos dois α. O palpite do `cenario.md` acertou a direção, mas não o tamanho: com
σ = 2,1 no log, quando um PR muito lento cai num grupo, ele puxa a média desse grupo e infla o
desvio padrão ao mesmo tempo, então o |t| quase não cresce e raramente passa do valor crítico. Um teste
conservador parece seguro, mas o mesmo motivo que segura o erro tipo I tira poder, que é o que a Q2
mede.

**Mann-Whitney: em α, a menos do sorteio.** A 1% fica dentro da faixa. A 5%, os 4,38% ficam um
pouco abaixo, mas isso é a semente: rodando 200.000 repetições com outra semente, a taxa sai em
4,88%. Essa sobra abaixo de 5% vem da correção de continuidade da aproximação normal de U, que
deixa o teste levemente conservador. A faixa de 95% também erra uma vez em vinte, e aqui são
quatro faixas: uma delas cair fora sem o teste ter problema não é surpresa. Para um teste em
postos, a cauda longa não importa: sob H₀ os grupos são idênticos, e qualquer ordem dos postos é
igualmente provável, seja qual for a distribuição.

## Q2: poder

Mesmo motor, mesmo cenário base, agora com o grupo com bot deslocado. O efeito zero é o mesmo
ponto da Q1, com a mesma semente, então as linhas coincidem no `simulacoes.csv`. A tabela é gerada
por `python -m lab04.simulacao.q2` e não deve ser editada à mão.

<!-- q2:inicio -->
10000 repetições por efeito, cenário base, semente 42. Efeito em log e como multiplicador da mediana do grupo com bot; a linha em negrito é o efeito dos dados reais.

| Efeito (log) | Mediana com bot | Welch, α = 5% | Mann-Whitney, α = 5% | Welch, α = 1% | Mann-Whitney, α = 1% |
|---|---|---|---|---|---|
| 0.000 | ×1 | 1.6% | 4.4% | 0.1% | 0.8% |
| 0.223 | ×1.25 | 2.1% | 6.6% | 0.1% | 1.5% |
| 0.405 | ×1.5 | 2.9% | 10.2% | 0.2% | 3.1% |
| 0.693 | ×2 | 5.6% | 22.1% | 0.4% | 8.0% |
| 0.916 | ×2.5 | 9.2% | 34.6% | 1.1% | 14.5% |
| 1.099 | ×3 | 12.1% | 47.0% | 1.4% | 23.7% |
| 1.386 | ×4 | 18.7% | 66.5% | 2.9% | 40.8% |
| **1.561** | **×4.76** | **23.5%** | **77.4%** | **4.3%** | **53.2%** |
| 1.609 | ×5 | 24.5% | 80.2% | 4.5% | 57.8% |
| 1.792 | ×6 | 28.6% | 86.2% | 5.7% | 66.7% |
| 2.079 | ×8 | 36.2% | 94.7% | 8.7% | 83.5% |
| 2.485 | ×12 | 45.9% | 99.2% | 13.7% | 95.5% |
| 2.996 | ×20 | 53.8% | 100.0% | 19.3% | 99.6% |
| 3.912 | ×50 | 62.4% | 100.0% | 26.2% | 100.0% |
| 4.605 | ×100 | 63.3% | 100.0% | 28.7% | 100.0% |

Efeito em que o poder chega a 80% (interpolado entre os pontos da grade):

- t de Welch, α = 5%: não chega, nem com a mediana ×100 (máximo 63.3%)
- Mann-Whitney, α = 5%: efeito 1.61 no log, mediana ×4.98
- t de Welch, α = 1%: não chega, nem com a mediana ×100 (máximo 28.7%)
- Mann-Whitney, α = 1%: efeito 2.02 no log, mediana ×7.54
<!-- q2:fim -->

**Mann-Whitney chega a 80% com a mediana do grupo com bot cerca de 5 vezes maior** (×7,5 a 1%) e
passa de 99% a partir de ×12. É a curva que a grade foi escolhida para cobrir: sai dos 5% da Q1 e
chega a 100%.

**O Welch não chega a 80% em nenhum efeito.** A curva sobe devagar e para em cerca de 65% a 5% (e
cerca de 30% a 1%), por maior que seja o efeito. O motivo é o mesmo que o deixou conservador na Q1.
Multiplicar os tempos do grupo com bot por m multiplica a média e o desvio padrão desse grupo pelo
mesmo m. Quando m fica grande, o grupo sem bot some da conta e o t vira x̄ / (s/√n) de uma amostra
só do grupo com bot, que não depende de m. Com σ = 2,1 no log, essa amostra tem cauda tão longa
que o desvio padrão costuma ser do tamanho da média, e o t passa do valor crítico só em cerca de
65% das amostras (conferido sorteando esse t de uma amostra só: 65,5% a 5% e 31,6% a 1%). Aumentar
o efeito não ajuda o Welch; só um n maior ajudaria, e o Mann-Whitney não tem esse teto, porque um
PR mil vezes mais lento conta nos postos como um PR só "mais lento".

**No efeito dos dados reais (×4,76)** o Mann-Whitney tem 77% de poder e o Welch 24%. Com 30 PRs
por grupo, se o efeito real for desse tamanho, o Mann-Whitney o detecta em três de cada quatro
amostras, e um Welch não significativo seria o resultado esperado, não evidência de que o bot não
muda nada. Para um efeito menor, de ×2, nem o Mann-Whitney passa de 22%: detectá-lo pediria bem
mais PRs por grupo.

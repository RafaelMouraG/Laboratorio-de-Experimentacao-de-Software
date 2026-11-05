# Cenário

Escrito antes de qualquer simulação. O histórico deste arquivo no git é a prova de que o palpite
veio antes dos resultados, e a seção 7 do dashboard confronta um com o outro.

## Pergunta

O tempo até o merge de um PR no `langflow-ai/langflow` muda quando o PR recebe review do
`coderabbitai[bot]`?

Seja X o tempo até o merge, em horas, de um PR com review do CodeRabbit e Y o de um PR sem esse
review. Os dois testes rodam sobre as horas brutas, sem tirar o log antes, porque é a escala em que
a pergunta é feita e em que alguém aplicaria o teste sem pensar duas vezes.

| Teste | H₀ | H₁ |
|---|---|---|
| t de Welch | E[X] = E[Y]: o tempo médio até o merge é o mesmo com e sem CodeRabbit | E[X] ≠ E[Y] |
| Mann-Whitney | P(X > Y) = P(Y > X): nenhum grupo tende a ter tempos maiores que o outro | P(X > Y) ≠ P(Y > X) |

## Unicaudal ou bicaudal

Bicaudal, nos dois testes. O bot pode acelerar o merge, porque o autor recebe retorno em minutos e
corrige antes do revisor humano chegar, ou atrasar, porque cada comentário a mais é mais uma rodada
de ajuste antes do merge. Não temos motivo para descartar um dos lados antes de ver os dados, e
escolher a cauda depois de olhar seria trapaça com o α.

## O que cada teste compara

- **Welch** compara médias. Não supõe variâncias iguais, mas supõe que a média amostral de cada
  grupo já seja quase normal. Com tempo até o merge, que tem cauda longa, um PR esquecido por
  semanas puxa a média e infla a variância, e o teste perde força.
- **Mann-Whitney** compara postos. Responde se, sorteando um PR de cada grupo, um tende a demorar
  mais que o outro. Não olha a média nem, a rigor, a mediana.

Os dois só respondem à mesma pergunta quando os grupos têm a mesma forma e diferem por um
deslocamento. No nosso modelo, isso é uma lognormal com o mesmo σ nos dois grupos e o efeito
somado ao μ (multiplicando todos os tempos pelo mesmo fator). Aí média, mediana e P(X > Y) mudam
juntas, e H₀ é verdadeira para os dois testes ao mesmo tempo, ou falsa para os dois.

Quando os σ diferem, as perguntas se separam. A média de uma lognormal é exp(μ + σ²/2), então dois
grupos com a mesma mediana e σ diferentes têm médias diferentes: H₀ do Welch é falsa, enquanto
P(X > Y) continua em 1/2 e H₀ do Mann-Whitney é verdadeira. Nessa situação (a quarta da Q3) uma
rejeição do Welch não é erro tipo I, e o Mann-Whitney deixa de ter a taxa de erro exata de α,
porque sua distribuição sob H₀ supõe grupos idênticos, não só P(X > Y) = 1/2.

## Parâmetros da simulação

Cada grupo vira uma lognormal com μ = média do log das horas e σ = desvio padrão desse log, ambos
calculados por `lab04/simulacao/parametros.py` a partir de `lab04/data/prs.csv`. A tabela abaixo é
gerada pelo script (`python -m lab04.simulacao.parametros`) e não deve ser editada à mão.

<!-- parametros:inicio -->
| Grupo | n | Mediana real (h) | μ = média do log | σ = desvio do log | exp(μ) (h) | Shapiro no log (p) |
|---|---|---|---|---|---|---|
| com_bot | 30 | 36.8 | 3.065 | 2.338 | 21.4 | 0.028 |
| sem_bot | 30 | 3.0 | 1.503 | 1.933 | 4.5 | 0.017 |

σ comum do cenário base: 2.136
<!-- parametros:fim -->

**Por que lognormal, mesmo com o Shapiro rejeitando a 5%.** O log das horas não é normal: é
bimodal, com um grupo de PRs mergeados em poucas horas e outro que leva dias ou semanas, e por isso
a mediana real do grupo com bot fica longe de exp(μ). Mesmo assim ficamos com a lognormal. A
rejeição é fraca, os p-valores ficam entre 1% e 5%, e com 30 PRs por grupo não dá para estimar com
segurança uma mistura de duas lognormais, que pede cinco parâmetros por grupo. A lognormal acerta o
que importa para os dois testes, a cauda longa à direita e a escala de cada grupo. A bimodalidade
fica como limitação e aparece no G1, onde o real é posto ao lado do simulado.

**Cenário base.** n igual ao coletado e um σ só para os dois grupos, a média dos dois σ, para que
efeito zero seja H₀ verdadeira para os dois testes. A diferença entre os σ observados é da ordem do
erro padrão de um desvio estimado com 30 pontos (cerca de σ/√58), então tratá-la como ruído é
razoável. Ela volta na quarta situação da Q3, com os grupos de mesma mediana e σ diferentes.

**O que os dados já mostram.** A mediana do grupo com bot é várias vezes a do grupo sem bot, e
só ele tem PRs passando de uma semana. Isso não muda o palpite abaixo, que é sobre o comportamento
dos testes, não sobre o efeito real, mas diz até onde as curvas de poder da Q2 precisam ir.

## Palpite

Antes de simular, apostamos no **Mann-Whitney**.

- **Erro tipo I, cenário base.** Os dois perto de 5%. O Mann-Whitney fica em α, a menos da
  aproximação normal de U, já que os grupos são idênticos sob H₀. O Welch deve ficar um pouco
  abaixo de 5% (conservador), porque com n igual a assimetria dos dois grupos se cancela, mas a
  cauda longa infla a variância.
- **Poder.** O Mann-Whitney chega a 80% com um efeito bem menor, e a diferença deve ser grande.
  Com σ do log perto de 2, a média de uma lognormal é mais de 7 vezes a mediana (exp(σ²/2)), e
  poucos PRs muito lentos dominam a média e o desvio padrão, então o sinal do deslocamento some no
  ruído do t. Nos postos, esses PRs contam só como "o mais lento", sem peso extra.
- **Q3.** Outliers e mais assimetria aumentam a vantagem do Mann-Whitney, mas o ganho deve ser
  menor do que pareceria, porque com o σ real o Welch já sai perdendo no cenário base. Com n = 10 os
  dois perdem poder, e o Welch fica mais conservador. Com a mesma mediana e σ diferentes, esperamos o Welch
  rejeitando bem acima de 5%, o que é certo para a pergunta dele, e o Mann-Whitney um pouco fora de
  5%. É o único ponto em que o Welch pode "ganhar", se a pergunta for sobre a média.

## Erro tipo I e tipo II

- **Tipo I:** concluir que o CodeRabbit muda o tempo até o merge quando não muda. Um time adotaria
  ou manteria o bot pagando a assinatura e o ruído nos PRs sem ganho, ou o grupo publicaria um
  efeito que não existe.
- **Tipo II:** não detectar um efeito que existe. O time abandonaria um bot que acelera o merge, ou
  não perceberia que ele atrasa.

Neste cenário o tipo I pesa mais. Os dados são observacionais: o bot não foi sorteado entre os PRs,
então mesmo um resultado correto não prova causa, e um falso positivo seria lido como evidência de
um efeito que nem a associação sustenta. O tipo II já é esperado com cerca de 30 PRs por grupo e
se resolve reportando o poder junto do p-valor: "não significativo com poder baixo" é inconclusivo,
não ausência de efeito.

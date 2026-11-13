# Roteiro da apresentação

Roteiro de apoio para responder às 15 perguntas olhando o [dashboard publicado](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/).
As seções e gráficos citados abaixo são os títulos numerados do dashboard. Cada resposta foi
mantida curta para caber em cerca de 30 segundos; qualquer integrante deve conseguir responder a
qualquer pergunta.

## Integrante A

### 1. Qual é a pergunta do estudo e quais são as hipóteses?

Queremos saber se o tempo até o merge muda quando um PR recebe review do CodeRabbit. O Welch testa
se as médias são iguais; o Mann-Whitney testa se um grupo tende a demorar mais que o outro.

**Onde:** [seção 1 — Pergunta e hipóteses](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#pergunta), bloco H₀/H₁.

### 2. De onde vêm os dados e quantas observações usamos?

São PRs mergeados do `langflow-ai/langflow`, entre agosto e outubro de 2026. Após filtros, sorteamos
30 com review do CodeRabbit e 30 sem; excluímos PRs abertos por bots, sincronizações e merges rápidos
demais para haver review.

**Onde:** [seção 1 — De onde vêm os dados / Quantas observações](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#pergunta).

### 3. Por que os testes são bicaudais?

O bot pode acelerar ou atrasar o merge: a correção antecipada pode ajudar, mas comentários também
podem criar mais rodadas de ajuste. Não havia justificativa para escolher uma direção antes de ver
os dados.

**Onde:** [seção 1 — Pergunta e hipóteses](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#pergunta).

### 4. O que diferencia Welch de Mann-Whitney neste estudo?

Welch compara médias em horas e é sensível à cauda longa. Mann-Whitney compara postos: pergunta se,
ao sortear um PR de cada grupo, um tende a demorar mais; não é, em geral, um teste de medianas.

**Onde:** [seção 1 — Pergunta e hipóteses](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#pergunta), H₀/H₁.

### 5. O que o G1 mostra sobre os tempos reais e simulados?

A mediana real foi 36,8 horas com bot e 3,0 sem. A simulação reproduz a cauda longa e o deslocamento,
mas não a bimodalidade dos dados reais, com PRs mergeados em poucas horas e outros em dias.

**Onde:** [seção 2 — G1: Tempos reais e simulados](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#g1), gráfico de distribuições.

## Integrante B

### 6. O que o G2 representa?

Ele mostra as distribuições das estatísticas sob a hipótese nula e destaca as áreas de p-valor do
conjunto simulado usado no G1. Nesse conjunto, os p-valores foram 0,1359 para Welch e 0,0022 para
Mann-Whitney; a 5%, só o segundo detectou o efeito inserido pelo gerador.

**Onde:** [seção 3 — G2: Distribuições das estatísticas sob H₀](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#g2).

### 7. O que o p-valor não significa?

Não é a probabilidade de H₀ ser verdadeira, nem a probabilidade de o resultado ter acontecido “por
acaso”. É a probabilidade, supondo H₀, de observar uma estatística tão extrema quanto ou mais
extrema que a obtida.

**Onde:** [seção 3 — G2](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#g2), áreas destacadas de p-valor.

### 8. O que seriam erros tipo I e tipo II no nosso cenário?

Tipo I seria concluir que o CodeRabbit muda o tempo quando não muda. Tipo II seria não detectar
uma mudança que existe. O primeiro pode levar o time a atribuir ao bot um efeito falso; o segundo,
a abandonar um bot potencialmente útil.

**Onde:** [seção 4 — G3: Erro tipo I](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#g3) e [seção 7 — Palpite, resultados e conclusão](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#conclusao).

### 9. Por que o Welch cometeu erro tipo II no exemplo do G1?

O efeito era verdadeiro por construção, mas poucos PRs muito lentos inflaram o desvio padrão e
esconderam o deslocamento da média. O Welch não rejeitou H₀; o Mann-Whitney, que usa postos,
rejeitou.

**Onde:** [seção 2 — G1](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#g1), leitura do gráfico, e [seção 3 — G2](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#g2).

### 10. O que é poder e o que a Q2 mostrou no efeito observado?

Poder é a chance de rejeitar H₀ quando o efeito existe. Para o efeito observado — mediana com bot
4,76 vezes maior — o poder a 5% foi 77,4% no Mann-Whitney e 23,5% no Welch; a 1%, 53,2% e 4,3%,
respectivamente.

**Onde:** [seção 5 — G4: Poder dos testes](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#g4), curva do cenário base.

## Integrante C

### 11. O que a simulação de erro tipo I revelou?

Com 10.000 repetições no cenário base, o Welch rejeitou 1,56% a α = 5% e 0,07% a α = 1%, sendo
conservador. O Mann-Whitney rejeitou 4,38% e 0,84%, taxas próximas dos níveis escolhidos, com a
diferença esperada pela aproximação usada.

**Onde:** [seção 4 — G3: Erro tipo I](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#g3), cenário base. A taxa do Mann-Whitney a 5% fica ligeiramente abaixo da faixa esperada; a de 1% fica dentro.

### 12. O que muda quando usamos α = 0,01?

O critério fica mais rigoroso: toleramos no máximo 1% de erro tipo I sob H₀, em vez de 5%, mas
também reduzimos o poder. Nos dados reais, p = 0,0107 do Welch não passa; p = 0,0099 do
Mann-Whitney passa por pouco.

**Onde:** [seção 6 — Os dois testes nos dados reais](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#dados-reais), tabela com p-valores e conclusões por α.

### 13. O que a Q3 ensina sobre assimetria, outliers, n pequeno e dispersões?

Assimetria, outliers e amostras pequenas prejudicam especialmente o poder do Welch. Em “Dispersões”,
os testes podem responder a perguntas diferentes: com medianas iguais, as médias ainda podem ser
diferentes se os grupos tiverem dispersões distintas.

**Onde:** [seção 5 — G4](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#g4), seletores das situações, e [seção 7 — comparação do palpite com a simulação](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#conclusao).

### 14. Qual teste escolheríamos e quando essa escolha mudaria?

Mann-Whitney: o poder dele é cerca de 77% tanto na lognormal quanto reamostrando os PRs reais. O do
Welch vai de 24% a 81% conforme o modelo da cauda, que 30 PRs não deixam medir. Se a pergunta fosse
sobre a média — horas totais de espera —, o teste certo seria o Welch.

**Onde:** [seção 7 — Conferindo o modelo / Qual teste usar neste cenário / Quando a escolha mudaria](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#conclusao).

### 15. Qual é a principal limitação da conclusão?

A lognormal exagera a cauda à direita: a média do modelo no grupo com bot é 330 h contra 129 h
reais, e isso derruba o Welch na simulação. Além disso, os dados são observacionais: o bot não foi
sorteado e há concentração de autoria, então o resultado é associação, não causa.

**Onde:** [seção 7 — Principal limitação](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#conclusao) e [seção 1 — dados reais](https://rafaelmourag.github.io/Laboratorio-de-Experimentacao-de-Software/#pergunta).

## Plano e registro do ensaio cronometrado

O roteiro reserva **20 segundos por resposta**, mais até **30 segundos** para abertura, transições e
encerramento: **5min30s no total**, dentro do limite de 7 minutos. Cada pessoa responde a cinco
perguntas. As respostas foram redigidas para caber no limite; use a tabela no ensaio para registrar
o tempo real e assinalar qualquer resposta que passe de 30 segundos.

| Integrante | Perguntas | Tempo-alvo das respostas | Tempo cronometrado | Passou de 30 s? |
|---|---:|---:|---|---|
| A | 1–5 | 1min40s | A registrar no ensaio com o grupo | A verificar |
| B | 6–10 | 1min40s | A registrar no ensaio com o grupo | A verificar |
| C | 11–15 | 1min40s | A registrar no ensaio com o grupo | A verificar |
| Abertura, transições e encerramento | — | Até 30s | A registrar no ensaio com o grupo | A verificar |
| **Total** | **15** | **Até 5min30s** | **A registrar no ensaio com o grupo** | **A verificar** |

**Registro pendente:** o tempo acima é a alocação do roteiro, não uma medição de ensaio. A
cronometragem real exige a participação dos três integrantes; anotem os tempos e revisem toda
resposta que passar de 30 segundos antes da apresentação.

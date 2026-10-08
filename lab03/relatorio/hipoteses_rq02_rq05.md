# Hipóteses informais: RQ 02 e RQ 05

> Escritas antes da coleta da amostra, sem ter calculado lead time nem CFR para nenhum repositório
> (os testes de #76 usam só fixtures feitas à mão).

**RQ 02 (lead time).**
Esperamos que a variante por release (a) fique bem acima da por commit (b), e que essa diferença
venha da própria definição. O commit mais antigo de uma release costuma ser um dos primeiros
escritos logo depois da release anterior, então (a) acaba medindo, na prática, o intervalo entre
duas releases, somado ao tempo que o PR mais antigo passou aberto. Com o filtro de ≥ 5 releases na
janela e bibliotecas populares soltando versão a cada poucas semanas, apostamos em (a) com mediana
entre 2 e 4 semanas (Medium), com uma parte grande, perto de um terço, já em Low (≥ 30 dias). Na
(b), os commits se espalham pelo intervalo inteiro, e os de perto da release puxam a mediana para
baixo: esperamos algo entre 40% e 60% de (a), com mediana perto de 1 semana, na fronteira entre
High e Medium. Duas coisas devem inflar a cauda de (a). A primeira é o commit antigo "esquecido",
de uma branch que ficou parada meses e entrou numa release. A segunda é o repositório que mantém
mais de uma linha de versão (`1.x` e `2.x` ao mesmo tempo): a release anterior pela data pode estar
em outra linha, e o `compare` traz commits que não têm nada a ver com aquela entrega. Na (b) esses
casos são poucos commits no meio de muitos e pesam pouco. Por isso esperamos (a) ≥ (b) em mais de
90% dos repositórios e a categoria DORA de lead time mudando entre as variantes em cerca de metade
deles, quase sempre para a categoria do lado.

**RQ 05 (frequência × taxa de falha).**
Achamos que as duas variantes vão dar respostas opostas, e que nenhuma das duas diz muito sobre o
*trade-off* do DORA. Com o CFR de CI (a), esperamos correlação fraca, |ρ| < 0,2, talvez levemente
negativa. Falhar no CI do `main` depende mais da saúde dos testes (teste instável, dependência
externa) do que de quantas releases o projeto solta, e o projeto que automatizou a publicação
costuma ser o mesmo que tem um CI bem cuidado. Isso iria a favor do DORA, mas fraco demais para
confirmar alguma coisa. Com o CFR de entrega (b), esperamos ρ positivo e moderado, entre 0,3 e 0,5,
o que pareceria um *trade-off*, mas boa parte disso vem da forma de medir. Uma release só "falha"
se vier outra em até 7 dias, e quem solta release toda semana quase sempre tem uma logo depois,
enquanto quem solta uma por mês quase nunca tem. Além disso, cada release corretiva conta ao mesmo
tempo como deploy na RQ 01, então um mesmo bug aumenta a frequência e o CFR de uma vez só. Se o ρ
da (b) vier positivo, não vamos ler isso como "ir rápido quebra mais", e sim como sinal de que o
proxy de entrega mistura frequência e falha.

**Nota para Metodologia / Resultados (não é hipótese):** esperamos muitos repositórios com CFR (b)
exatamente 0, sobretudo os que soltam poucas releases. Isso gera muitos empates nos postos, o que o
Spearman aguenta, mas tira poder do teste e faz o gráfico de dispersão virar uma linha no eixo x.
Vale reportar quantos repositórios têm CFR (b) = 0 junto com o ρ, e usar escala log só no eixo da
frequência.

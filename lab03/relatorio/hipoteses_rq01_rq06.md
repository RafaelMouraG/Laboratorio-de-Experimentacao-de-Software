# Hipóteses informais: RQ 01 e RQ 06

> Escritas antes da coleta da amostra, sem ter calculado a frequência de
> deploy nem comparado os subgrupos da amostra final.

**RQ 01 (frequência de deploy).**
Esperamos que a frequência de deploy, medida por releases publicadas por
semana, fique concentrada entre as categorias *Medium* e *High*, isto é,
entre 1 release por mês e 7 releases por semana. Apostamos em uma mediana
mais próxima do limite inferior de *Medium* do que da frequência diária da
categoria *Elite*, porque muitos repositórios populares são bibliotecas ou
frameworks que agrupam várias mudanças antes de publicar uma versão. Assim,
não esperamos releases diárias na maioria dos projetos, embora uma parcela
menor possa alcançar *Elite* por possuir publicação automatizada. Também
esperamos uma cauda de valores baixos e uma distribuição assimétrica: alguns
projetos podem publicar muitas versões, enquanto outros, apesar de usarem
CI/CD, lançam versões apenas mensalmente ou com intervalos maiores. Por isso,
a mediana e o IQR devem representar melhor o comportamento típico do que a
média.

**RQ 06 (características associadas ao desempenho DORA).**
Esperamos que repositórios mais populares, mais antigos e com mais
contribuidores apresentem melhor desempenho DORA, especialmente maior
frequência de deploy e menor *lead time*. A justificativa é que visibilidade
e maturidade tendem a favorecer automação, processos de revisão e capacidade
de manutenção. Para esses fatores, esperamos diferenças entre os grupos em
pelo menos algumas métricas, mas com tamanhos de efeito pequenos ou
moderados, e não uma separação completa entre as categorias DORA.

Não esperamos que a associação seja uniforme nas quatro métricas. A idade
pode indicar experiência e processos mais maduros, mas também pode estar
associada a maior complexidade e dívida técnica, elevando o *lead time* ou o
tempo de recuperação. Da mesma forma, a popularidade pode favorecer
automação e aumentar a capacidade de manutenção, mas também ampliar a
superfície de uso e a quantidade de mudanças problemáticas. Também esperamos
diferenças entre linguagens e tipos de projeto, mas sem assumir que uma
linguagem seja causalmente superior às demais. Portanto, esperamos
associações parciais e dependentes da métrica, e não que uma única
característica explique todo o desempenho DORA.

**Nota para Resultados / Ameaças à validade (não é hipótese):** a RQ 06
envolve várias combinações de fatores e métricas. Os resultados devem ser
interpretados depois da correção de Holm e em conjunto com os tamanhos de
efeito. Subgrupos pequenos, quartis com muitos empates e o uso de releases
como proxy de deploy podem reduzir a força das associações observadas.

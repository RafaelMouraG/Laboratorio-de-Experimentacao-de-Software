# Notas para as próximas seções do artigo

Observações que saíram junto com as hipóteses (#81), mas que não são hipótese. Ficam aqui até
entrarem na seção certa do `artigo.tex`.

## Retenção do histórico de runs (Metodologia / Ameaças à validade)

Testando a coleta, janeiro a junho de 2025 voltou 0 workflow runs para `psf/requests` e
`pallets/flask`, que têm CI ativo, enquanto abril a setembro de 2026 voltou normal. O GitHub não
parece guardar o histórico de runs antigos. Se a janela começar muito no passado, os primeiros
meses podem vir vazios, o que derruba repositório no filtro de ≥ 50 runs e mexe na CFR (a). Vale
confirmar o tempo de retenção antes da coleta completa. *(Mateus)*

## CFR (b) igual a zero e o Spearman (Resultados da RQ 05)

Esperamos muitos repositórios com CFR (b) exatamente 0, sobretudo os que soltam poucas releases.
Isso gera muitos empates nos postos, o que o Spearman aguenta, mas tira poder do teste e faz o
gráfico de dispersão virar uma linha no eixo x. Vale reportar quantos repositórios têm CFR (b) = 0
junto com o ρ, e usar escala log só no eixo da frequência. *(Rafael)*

## Muitos testes na RQ 06 (Resultados / Ameaças à validade)

A RQ 06 envolve várias combinações de fatores e métricas. Os resultados devem ser interpretados
depois da correção de Holm e em conjunto com os tamanhos de efeito. Subgrupos pequenos, quartis com
muitos empates e o uso de releases como proxy de deploy podem reduzir a força das associações
observadas. *(Athos)*

## Confusão entre fatores e subgrupos na RQ 06 (Ameaças à validade)

Os fatores da RQ 06 foram testados um de cada vez, e idade e contribuidores andam juntos (Spearman
ρ = 0,46). O efeito dos contribuidores no lead time (a) aparece só no 4º quartil e pode ser o da
idade. A linguagem também carrega idade: C++ tem mediana de 11,8 anos e 57 dos 78 repositórios do
quartil mais novo são Python ou TypeScript. O corte de 10 repositórios por linguagem é nosso e deixa
C++ (16) e Java (11) com grupos pequenos, enquanto "Outras" junta 17 linguagens diferentes (38
repositórios). Os empates nos contribuidores (272 valores distintos em 310) deixam os quartis com 76
a 79 repositórios, o que não muda a conclusão. O tipo de projeto só existe nos 60 da amostra-ouro, e
59 repositórios em três grupos não têm poder para mostrar efeitos pequenos. *(Rafael)*

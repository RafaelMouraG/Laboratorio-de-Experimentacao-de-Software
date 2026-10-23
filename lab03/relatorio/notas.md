# Notas para as próximas seções do artigo

Observações que saíram junto com as hipóteses (#81), mas que não são hipótese. Ficam aqui até
entrarem na seção certa do `artigo.tex`.

## Retenção do histórico de runs (Metodologia / Ameaças à validade)

**Situação (S03):** não usado; vai para Ameaças à validade na entrega final.

Testando a coleta, janeiro a junho de 2025 voltou 0 workflow runs para `psf/requests` e
`pallets/flask`, que têm CI ativo, enquanto abril a setembro de 2026 voltou normal. O GitHub não
parece guardar o histórico de runs antigos. Se a janela começar muito no passado, os primeiros
meses podem vir vazios, o que derruba repositório no filtro de ≥ 50 runs e mexe na CFR (a). Vale
confirmar o tempo de retenção antes da coleta completa. *(Mateus)*

## CFR (b) igual a zero e o Spearman (Resultados da RQ 05)

**Situação (S03):** usado na RQ 05 (59 repositórios com CFR (b) = 0 e o ρ sem eles).

Esperamos muitos repositórios com CFR (b) exatamente 0, sobretudo os que soltam poucas releases.
Isso gera muitos empates nos postos, o que o Spearman aguenta, mas tira poder do teste e faz o
gráfico de dispersão virar uma linha no eixo x. Vale reportar quantos repositórios têm CFR (b) = 0
junto com o ρ, e usar escala log só no eixo da frequência. *(Rafael)*

## Muitos testes na RQ 06 (Resultados / Ameaças à validade)

**Situação (S03):** o Holm entrou nos Resultados; o resto vai para Ameaças à validade na entrega final.

A RQ 06 envolve várias combinações de fatores e métricas. Os resultados devem ser interpretados
depois da correção de Holm e em conjunto com os tamanhos de efeito. Subgrupos pequenos, quartis com
muitos empates e o uso de releases como proxy de deploy podem reduzir a força das associações
observadas. *(Athos)*

## Confusão entre fatores e subgrupos na RQ 06 (Ameaças à validade)

**Situação (S03):** parte está na Discussão da RQ 06; o resto vai para Ameaças à validade na entrega final.

Os fatores da RQ 06 foram testados um de cada vez, e idade e contribuidores andam juntos (Spearman
ρ = 0,46). O efeito dos contribuidores no lead time (a) aparece só no 4º quartil e pode ser o da
idade. A linguagem também carrega idade: C++ tem mediana de 11,8 anos e 57 dos 78 repositórios do
quartil mais novo são Python ou TypeScript. O corte de 10 repositórios por linguagem é nosso e deixa
C++ (16) e Java (11) com grupos pequenos, enquanto "Outras" junta 17 linguagens diferentes (38
repositórios). Os empates nos contribuidores (272 valores distintos em 310) deixam os quartis com 76
a 79 repositórios, o que não muda a conclusão. O tipo de projeto só existe nos 60 da amostra-ouro, e
59 repositórios em três grupos não têm poder para mostrar efeitos pequenos. *(Rafael)*

## RQ 09: limites da detecção e do desenho (Ameaças à validade)

**Situação (S03):** não usado; vai para Ameaças à validade na entrega final.

- A detecção só enxerga quem deixa rastro: quem usa IA sem marca conta como não adotante, o que
  aproxima os grupos. A precisão foi medida (100% no consenso, 89,7% a 100% por avaliador), o recall
  não.
- O grupo sem IA tem só 28 repositórios, e todo resultado significativo da análise 1 vem da
  comparação com ele. Repositório mais ativo tem mais chance de ter algum commit marcado.
- O primeiro commit com IA só é procurado na janela; quem já usava antes de outubro de 2025 aparece
  como adotante no primeiro dia. A regra de 91 dias de cada lado tira 162 repositórios da análise 2.
- A lista de ferramentas de IA da robustez foi feita à mão, e o resultado muda conforme ela.
- A análise 3 (#119) cruzou commits com IA e métricas antes do commit da regra dos níveis
  (`5dc0c72`); o pré-registro vale para as análises 1 e 2.
- Sem grupo de controle, a queda de tendência do lead time (b) depois da adoção não se separa de uma
  tendência geral do período.

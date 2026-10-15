# Protocolo de rotulagem da amostra-ouro

A heurística de release corretiva (#96) decide sozinha se uma release existe para corrigir um
defeito, e é isso que define a CFR (b). Para saber o quanto ela erra, a gente compara com o
julgamento de pessoas. Cada um dos três rotula a mesma amostra por conta própria; depois a #97 mede
o quanto concordamos (kappa de Fleiss) e monta o consenso, que vira o gabarito da heurística.

O tipo do projeto rotulado aqui também é um dos fatores da RQ 06.

## O que foi sorteado

`python -m lab03.validacao.sortear` sorteia 60 repositórios de `lab03/data/repos.csv`
(`sample(n=60, random_state=42)`) e, em cada um, 5 releases da janela com a mesma semente. Só
entram releases que têm uma release anterior e cujo compare com ela existe, porque sem isso não há
lista de commits para ler. Rodar o script de novo sorteia exatamente as mesmas.

## Suas planilhas

Em `rotulos/`, cada um tem duas, com o próprio login no nome:

| Arquivo | Uma linha por | Você preenche |
|---|---|---|
| `<login>_repos.csv` | repositório (60) | `tipo_projeto`, `entregas_reais` |
| `<login>_releases.csv` | release (300) | `corretiva` |

`observacao` é opcional e serve para a reunião de consenso: escreva ali quando ficar em dúvida ou
quando a decisão dependeu de algo que não está óbvio.

Abra no Google Sheets, Excel ou LibreOffice e salve de volta como CSV (UTF-8, separado por
vírgula). Os valores vão exatamente como estão abaixo, em minúsculas e sem acento; a #97 recusa
qualquer outra grafia.

## `tipo_projeto`

O que o projeto é para quem usa, olhando o começo do README.

| Valor | Quando | Exemplos |
|---|---|---|
| `biblioteca` | Código feito para ser importado por outro código: biblioteca, framework, SDK, plugin, componente de UI | `pallets/flask`, `psf/requests` |
| `aplicacao` | Algo que a pessoa abre ou roda como produto: app desktop, web ou mobile, servidor, banco de dados, serviço | `microsoft/vscode`, `excalidraw/excalidraw` |
| `cli` | Ferramenta usada principalmente pelo terminal | `cli/cli`, `BurntSushi/ripgrep` |
| `outro` | Nada acima: documentação, curso, lista de links, modelo de IA, conjunto de dados, configuração | `public-apis/public-apis`, `codecrafters-io/build-your-own-x` |

Projeto que é duas coisas (um framework que traz uma CLI, um banco que também é biblioteca): vale o
uso que o README apresenta primeiro.

## `entregas_reais`

As releases chegam de fato a quem usa o projeto? É o que separa uma release que funciona como
deploy de uma que é só uma marcação no histórico.

| Valor | Quando |
|---|---|
| `sim` | A release vem com algo instalável ou publicado (pacote no PyPI ou npm, binário, imagem Docker, instalador), ou é a versão que os usuários de fato atualizam |
| `nao` | A release não muda nada para quem usa: marco interno, snapshot automático sem notas, ou o projeto entrega por outro caminho (site com deploy contínuo) e a release só acompanha |
| `incerto` | Olhando a página de releases e o README por uns 2 minutos, não dá para decidir |

## `corretiva`

Pelo enunciado, uma release corretiva é aquela cujo **objetivo principal** é corrigir um defeito
recente. Leia as notas da release (`url_release`) e a lista de commits desde a anterior
(`url_compare`).

| Valor | Quando |
|---|---|
| `sim` | As notas e os commits são quase só correção: "Bug fixes", `fix:`, `hotfix`, `revert`, regressão, falha de segurança corrigida. Pode ter uma ou outra coisa a mais, desde que a correção seja o motivo da release |
| `nao` | Traz funcionalidade nova ou mudança de comportamento, mesmo que venha junto com correções; release de rotina que mistura tudo; só atualização de dependência, documentação ou CI sem defeito por trás |

Dois cuidados:

- **Não decida pelo número da versão.** Uma `x.y.1` não é corretiva só por ser patch, e uma
  `x.y.0` pode ser. Olhar o número é exatamente o que a heurística faz; a rotulagem existe para
  conferir se isso funciona.
- Release sem notas e com poucos commits: decida pela mensagem dos commits. Se nem eles ajudarem,
  marque `nao` e explique em `observacao`.
- Compare com milhares de commits: pode ser uma release grande de verdade, mas muitas vezes a
  release anterior pela data é de outra linha de versão (no elasticsearch, `v9.2.8...v8.19.14` tem
  5.188 commits). Nesse caso a lista não ajuda; decida pelas notas da release e anote
  `outra linha` em `observacao`.

## Regras

1. Rotule sozinho. Nada de conversar com os outros dois sobre algum caso antes de todos
   terminarem; as divergências são discutidas depois, na #97.
2. Não abra as planilhas dos outros até as três estarem commitadas.
3. Não rode a heurística (#96) nas releases da amostra antes de terminar a sua planilha.
4. Commite só o seu arquivo, na sua issue de rotulagem (#93, #94 ou #95).

## Consenso

Depois que os três integrantes terminarem a rotulagem, `python -m lab03.validacao.concordancia`
valida os arquivos e calcula o kappa de Fleiss e a concordância simples para cada dimensão. Um
item recebe automaticamente o rótulo que aparece em pelo menos duas das três planilhas (maioria
simples).

Quando os três rótulos são diferentes (`1-1-1`), o item é copiado para `empates.csv`. A reunião
de consenso preenche nesse mesmo arquivo as colunas `decisao` e `justificativa`; a decisão deve
ser um dos valores permitidos para a dimensão e a justificativa deve registrar o critério usado.
Uma nova execução preserva essas decisões e as aplica em `consenso_repos.csv` ou
`consenso_releases.csv`. Empates sem decisão continuam com o consenso vazio e ficam explicitamente
pendentes no arquivo de empates.

O kappa é acompanhado da porcentagem de concordância simples e da faixa de Landis & Koch. Kappa
baixo não é tratado como erro: indica ambiguidade do critério e deve ser discutido no artigo.

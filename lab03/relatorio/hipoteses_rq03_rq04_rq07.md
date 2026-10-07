# Hipóteses informais: RQ 03, RQ 04 e RQ 07

> Escritas antes da coleta da amostra. Os únicos números que vimos até aqui são de 3 repositórios
> usados só para testar o pipeline (`psf/requests`, `pallets/flask`, `microsoft/vscode`), que não
> entram na análise.

**RQ 03 (taxa de falha).**
Nossa aposta é que as duas variantes vão contar histórias diferentes. Pelo CI (a), a taxa deve sair
baixa, com mediana dentro de Elite (≤ 15%). O motivo é simples: em projeto popular quase nada chega
no `main` sem passar por um PR com o CI rodando, então o push no branch principal é, na prática, a
segunda vez que aquela build roda. O que ainda falha ali deve ser mais teste instável e dependência
externa mudando do que código quebrado de verdade. Já pela entrega (b), esperamos um número maior,
na faixa High (15% a 30%), porque é muito comum uma biblioteca soltar a `x.y.0` e, dois ou três dias
depois, a `x.y.1` com o que os usuários reportaram. Se isso se confirmar, CI verde não quer dizer
release sem problema, e as duas variantes vão ter pouca correlação entre si.

**RQ 04 (tempo de recuperação).**
Esperamos mediana entre 1 hora e 1 dia (High). CI vermelho no `main` trava o PR de todo mundo, então
alguém vai lá e resolve rápido, muitas vezes só rodando de novo o job que falhou por instabilidade.
O problema deve estar na cauda: workflow de documentação, lint ou publicação pode ficar quebrado por
semanas sem ninguém olhar, porque não bloqueia ninguém. Por isso esperamos um IQR largo e os
episódios censurados concentrados nesses workflows secundários, não no de testes.

**RQ 07 (sensibilidade à definição).**
Achamos que a classificação vai mudar bastante dependendo da definição: algo entre 30% e 50% dos
repositórios trocando de categoria em pelo menos um dos pares, com kappa ponderado moderado (0,40 a
0,60). O que mais deve pesar é a unidade de deploy. Muito projeto cria tag e não publica release, e
aí trocar release por tag (C3) faz a frequência subir e o repositório pular de categoria. Mas
esperamos que essas trocas sejam quase sempre para a categoria do lado (Elite → High, High →
Medium), quase nunca de Elite para Low. Se for assim, dá para confiar nas conclusões das RQ 01 a 06
como tendência geral, mas não na categoria exata de cada repositório.

**Nota para Metodologia / Ameaças à validade (não é hipótese):** testando a coleta, janeiro a junho
de 2025 voltou 0 workflow runs para `psf/requests` e `pallets/flask`, que têm CI ativo, enquanto
abril a setembro de 2026 voltou normal. O GitHub não parece guardar o histórico de runs antigos. Se
a janela começar muito no passado, os primeiros meses podem vir vazios, o que derruba repositório no
filtro de ≥ 50 runs e mexe na CFR (a). Vale confirmar o tempo de retenção antes da coleta completa.

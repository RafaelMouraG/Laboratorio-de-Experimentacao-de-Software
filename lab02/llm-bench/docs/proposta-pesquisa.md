# Proposta de pesquisa

Versão 0.1 — 24/09/2026. Registro da proposta discutida por Rafael e pela IA auxiliar. Documento de trabalho, ainda não congelado para coleta.

## 1. Finalidade e posição do estudo

Criar um mini benchmark exploratório, em repositório próprio, complementar ao lab02 obrigatório. O lab02 permanece separado e não é substituído por este estudo.

A finalidade proposta é caracterizar e comparar resultados de configurações completas de agentes de programação sob a perspectiva de desenvolvedores que precisam revisar e utilizar as entregas. A comparação considera correção funcional, robustez, manutenibilidade e eficiência.

O objeto comparado é a combinação **modelo + harness + skills**, incluindo suas configurações efetivas. As diferenças entre harnesses são intencionais. O desenho não permite atribuir isoladamente um resultado ao modelo, ao harness ou às skills.

A [GQM](gqm.md) orientará as decisões posteriores. Neste documento:

- **Diretriz acordada** registra uma condição expressa na discussão.
- **Proposta metodológica** registra uma recomendação incorporada para detalhamento antes da coleta.
- **Pendente** indica uma decisão ou validação ainda necessária.

## 2. Participantes pretendidos

Os rótulos abaixo preservam os nomes informados por Rafael. Não representam confirmação de disponibilidade, identificadores de API ou suporte aos níveis de raciocínio.

Atualização de 24/09/2026: a [verificação inicial do ambiente](verificacao-ambiente.md) registra identificadores encontrados, versões instaladas e variantes expostas. A tabela abaixo continua representando a intenção; o acesso em execução dentro dos containers ainda não foi validado.

| Rótulo informado | Harness pretendido | Configuração informada | Estado |
|---|---|---|---|
| Opus 5.5 | Claude Code | high | Selecionado; validar execução isolada |
| GPT Sol 6 | Codex | high | Selecionado; executar por último no piloto para preservar a cota disponível |
| Muse Spark 1.3 Contributor Free | OpenCode | xhigh | Rota Contributor Free confirmada por Rafael; validar execução isolada |
| MiMo-V2.6-Flash Free | OpenCode | sem variante; o catálogo não expõe esforço | **Retirado por Rafael** depois de duas entregas vazias no piloto com a tarefa real; sem substituto |
| Astra (`gpt-6-astra`) | Codex | high | Incluído por Rafael na coleta oficial em 24/09/2026, depois da entrega aceita no piloto com a tarefa real |

Decisão de Rafael em 24/09/2026: Sol em high, Muse na rota Contributor Free e Gemini em high. Ordem do piloto: Opus, Muse, Gemini e Sol por último. Essa ordem operacional do piloto não define a ordem das futuras repetições oficiais.

Nova decisão de Rafael, no mesmo dia: Gemini 3.8 Flash descartado, após duas tentativas sem entrega no piloto, e substituído por MiMo-V2.6-Flash Free (`opencode/mimo-v2.6-flash-free`) no OpenCode. A rota gratuita é oferecida "por tempo limitado", e os dados coletados nesse período podem ser usados para melhorar o modelo. As duas condições precisam constar do protocolo. Os detalhes estão no [registro do piloto](piloto-infraestrutura.md).

Terceira decisão de Rafael, no mesmo dia: MiMo-V2.6-Flash Free retirado depois do [piloto com a tarefa real](piloto-tarefa-real.md). Nas duas tentativas, o modelo esgotou o limite de 32 mil tokens de saída num único passo de raciocínio, antes de escrever qualquer arquivo, e as entregas ficaram vazias. O catálogo não oferece nível de esforço para limitar esse comportamento. As tentativas continuam no registro.

Quarta decisão de Rafael, no mesmo dia: o MiMo não terá substituto. A coleta segue com três participantes: Opus, Sol e Muse. As alternativas gratuitas avaliadas no OpenCode (Nemotron 3 Ultra, Ling 3.0 Flash e Nemotron 3.5 Lightning) não foram adotadas.

Quinta decisão de Rafael, no mesmo dia: Astra (`gpt-6-astra`, esforço `high`, no Codex) entra na coleta oficial, depois de ter a entrega aceita no [piloto com a tarefa real](piloto-tarefa-real.md). A coleta passa a ter quatro participantes: Opus, Sol, Astra e Muse. Sol e Astra compartilham harness, conta e esforço e diferem só no modelo; isso permite comparar dois modelos com o harness fixo, mas os dois consomem a mesma cota do ChatGPT.

Outras decisões de Rafael de 24/09/2026, depois do piloto com a tarefa real:

- **Prazo por tentativa:** 1800 s. As entregas aceitas levaram de 197 s a 602 s. O runner registra também todos os dados de recursos disponíveis no container.
- **Q9 adotada:** o desempenho da API entregue entra no foco de qualidade ([GQM](gqm.md)). O perfil de carga de M16 foi adotado com `DATA_DIR` em disco.
- **Binários dos harnesses:** fixados em disco, com hash, em vez de copiados do host a cada build ([runtime](../infra/runtime/README.md)).
- **Paridade entre harnesses:** as diferenças observadas no piloto são documentadas, não corrigidas ([runner](../infra/attempt/README.md), §5).
- **Aceitação:** não precisa distinguir as configurações. Espera-se que modelos de fronteira passem; a comparação se apoia em tempo, consumo, stack, desempenho e revisão qualitativa.
- **Repetições:** uma tentativa por configuração na coleta oficial. Consequências na [GQM](gqm.md), §4.
- **Cota:** as tentativas do piloto não chegaram perto do limite da sessão; a cota compartilhada de Sol e Astra não é uma restrição prática.

Antes da coleta, será necessário registrar, por configuração: provedor, identificador solicitado e identificador efetivo quando observável, nível de raciocínio, versão do harness, parâmetros relevantes, arquivos de configuração e manifesto das skills. Aliases mutáveis e configurações não observáveis deverão ser declarados como limitações.

## 3. Tarefa e condições ainda em definição

**Tarefa candidata:** implementar uma API de encurtador de URL, com stack livre e contrato HTTP fechado antes das execuções oficiais.

Ainda não foram definidos endpoints, persistência, regras de negócio, casos de erro, requisitos de segurança, concorrência, desempenho ou funcionalidades adicionais. Esses itens não devem ser inferidos como obrigações dos participantes.

Atualização de 24/09/2026: o [contrato candidato](contrato-encurtador.md) propõe endpoints, regras de validação, consistência e durabilidade. Ele ainda aguarda revisão de Rafael. O contrato também registra um bloqueio: a imagem atual não permite stack livre.

A formulação candidata da GQM prevê prazo limitado; o valor e a forma de aplicação desse limite permanecem pendentes. O escopo definitivo será escolhido depois do refinamento da GQM.

## 4. Isolamento e materiais — diretrizes acordadas

- Um container novo por tentativa, com o agente inteiro executado dentro dele.
- Sem acesso a outras entregas, testes reservados, histórico de outras tentativas ou memórias.
- Skills globais selecionadas, revisadas e copiadas explicitamente, com versões congeladas e diferenças entre ferramentas documentadas.
- Repositório central privado durante a coleta; participantes recebem somente os materiais de sua própria tentativa.
- Avaliação realizada sobre entregas congeladas.

O pacote entregue a cada participante deverá conter apenas o enunciado, os materiais e as instruções autorizados pelo protocolo. Não se deve montar o repositório central inteiro no container da tentativa.

**Proposta metodológica:** identificar por hashes os pacotes de entrada, skills, configurações exportáveis e artefatos entregues. Registrar a imagem e os limites do container, horários, eventos e versões do avaliador. Credenciais devem ser disponibilizadas pelo mecanismo mínimo necessário, sem incorporar segredos aos artefatos ou registros versionados. O mecanismo concreto de autenticação ainda será validado.

## 5. Avaliação — diretrizes e propostas

As evidências automatizadas terão prioridade. Rafael e a IA auxiliarão na avaliação; a revisão qualitativa será anonimizada, e a IA não será o único árbitro. A rubrica será definida antes das execuções oficiais.

Propostas metodológicas incorporadas:

1. Usar a aceitação integral da entrega como resultado principal, acompanhada do atendimento por requisito para mostrar resultados parciais.
2. Separar cobertura da avaliação, requisitos efetivamente avaliados e atendimento observado na entrega.
3. Associar os testes reservados a comportamentos dedutíveis da especificação recebida; casos reservados não introduzem obrigações novas.
4. Apresentar um perfil por configuração, sem nota geral agregada na proposta atual. Tempo, custo, correção e rubrica têm significados distintos.
5. Definir níveis qualitativos com critérios observáveis, apresentar resultados por dimensão e registrar evidências e divergências entre avaliações.
6. Distinguir falhas da entrega de falhas do experimento. Exclusões e substituições precisam de regras anteriores à coleta e de registro auditável.
7. Avaliar o artefato congelado sem reparos. Eventuais correções posteriores constituem outro resultado e não substituem a avaliação original.

A anonimização deverá remover identificadores do participante dos materiais de revisão sem alterar o código avaliado. A correspondência entre identificadores anônimos e configurações ficará separada. Indícios de autoria que permaneçam no artefato devem ser registrados como limitação; anonimização não garante cegamento perfeito.

## 6. Piloto de infraestrutura

Docker foi confirmado por consulta ao daemon e uma checagem básica com dois containers descartáveis passou; os detalhes e limites estão na [verificação inicial do ambiente](verificacao-ambiente.md). Ainda falta validar autenticação e execução de cada ferramenta **dentro dos containers**; funcionamento no host não comprova esse requisito.

Atualização de 24/09/2026: o [registro do piloto](piloto-infraestrutura.md) mostra, dentro dos containers, execução válida de Opus, Muse e MiMo. O Gemini falhou duas vezes, primeiro com HTTP 503 do provedor e depois por timeout, e foi descartado. Sol ainda não foi executado.

O piloto deverá verificar:

- Autenticação e execução dos harnesses com os modelos e parâmetros pretendidos.
- Isolamento de arquivos, histórico e memórias, além do carregamento das skills selecionadas.
- Aplicação dos limites escolhidos e comportamento ao encerrar uma tentativa.
- Coleta de logs, tempos e dados de consumo disponíveis, sem segredos.
- Exportação, identificação e congelamento da entrega, seguidos de avaliação em ambiente limpo.

Proposta: manter resultados do piloto fora da análise oficial e usar uma tarefa de verificação distinta da tarefa definitiva sempre que viável. O piloto valida a infraestrutura e a observabilidade das métricas; não deve ser usado para escolher condições que favoreçam uma configuração. Mudanças motivadas pelo piloto serão registradas antes do congelamento do protocolo.

## 7. Decisões em aberto

| Tema | Definição ou validação necessária |
|---|---|
| Participantes | Conjunto definido em 24/09/2026: Opus, Sol, Astra e Muse, todos validados no piloto com a tarefa real. Falta congelar os manifestos de configuração |
| Escopo | Contrato HTTP, requisitos obrigatórios e situações de robustez |
| Repetições | Decidido em 24/09/2026: uma tentativa por configuração. Falta definir a ordem das execuções |
| Prazo e recursos | Prazo por tentativa decidido em 24/09/2026: 1800 s. CPU, memória e demais limites continuam provisórios |
| Rede | Acesso permitido a provedores, pacotes, documentação e outros serviços |
| Skills | Seleção, revisão, versões e diferenças entre ferramentas |
| Assistência humana | Intervenções permitidas, registro e efeito na interpretação |
| Operação | Autenticação, falhas de infraestrutura, interrupções e política de substituição |
| Avaliação | Rubrica, testes, critérios de aceitação, anonimização e resolução de divergências |
| Medição | Fronteiras do tempo medido, atribuição de custo e dados indisponíveis; tabela de preços para a estimativa de custo; adoção de Q8. Q9 e o perfil de carga foram adotados em 24/09/2026 |
| Congelamento | Versões dos materiais, avaliador e procedimento para corrigir defeitos do próprio estudo |

## 8. Alcance das conclusões

As conclusões deverão se restringir às configurações, tarefa e condições observadas. Uma tarefa não representa todo o desenvolvimento de software. Repetições da mesma tarefa permitem observar sua variabilidade, mas não ampliam automaticamente a diversidade de problemas estudados.

A stack escolhida faz parte do caminho pelo qual a configuração produz sua entrega. Comparações de tamanho ou de métricas estruturais entre linguagens não serão interpretadas automaticamente como diferenças de qualidade.

Com poucas repetições, a análise deverá privilegiar resultados individuais, frequências e dispersão descritiva. Qualquer procedimento inferencial dependerá do desenho e de seus pressupostos; a escala de uma métrica, sozinha, não torna um teste estatístico apropriado.

## 9. Contribuições do material das aulas

Fonte lida: *Resumo Aulas 1, 2, 4 e 5: Medição de Software*, 16 páginas, datado de 23/09/2026. O arquivo se apresenta como resumo das aulas de Medição e Experimentação do Prof. Danilo Maia.

Arquivo consultado localmente: `/home/rafael-moura/Downloads/Resumo Aulas 1, 2, 4 e 5 Medição de Software.pdf`. O PDF não foi copiado para este repositório; esse caminho é apenas um registro de origem no computador de Rafael.

| Conteúdo e páginas | Incorporação à proposta |
|---|---|
| GQM: objetivo, perguntas e métricas — pp. 3–4 e 10 | Exigir rastreabilidade de cada métrica a uma pergunta e ao objetivo |
| Processo, produto e recurso — p. 7 | Identificar a entidade e a unidade de observação de cada medida |
| Atributos internos e externos — p. 7 | Distinguir propriedades do código de indícios de manutenibilidade |
| Escalas e operações admissíveis — pp. 8–10 | Especificar a escala; tratar a rubrica como ordinal, sem pressupor distâncias iguais |
| Goodhart, McNamara e métricas manipuláveis — pp. 1–3 e 6 | Combinar evidências; evitar volume de código e cobertura isolada como metas de qualidade |
| Cobertura de requisitos por testes — p. 12, item 89 | Separar abrangência do avaliador e atendimento da entrega |
| Limitações de LOC e tamanho funcional — pp. 10–12 | Comparar comportamento contratual, evitando LOC como produtividade entre stacks |
| Processo de medição — p. 7 | Definir fonte, coleta, cálculo, interpretação e conservação dos dados |

O resumo será usado como apoio conceitual e mapa bibliográfico. Atribuições a normas e fórmulas apresentadas como inspiradas em normas deverão ser verificadas nas fontes originais antes de serem usadas como fundamentação normativa.

DORA, CMMI, Team Topologies, COCOMO, MTBF e disponibilidade não entram como métricas centrais nesta proposta. Seu uso exigiria perguntas e condições de observação que ainda não fazem parte do estudo.

Referência primária de GQM consultada: Basili, V. R.; Caldiera, G.; Rombach, H. D. (1994). *The Goal Question Metric Approach*. Encyclopedia of Software Engineering, pp. 528–532. [Texto disponibilizado pela University of Maryland](https://www.cs.umd.edu/~basili/publications/technical/T89.pdf).

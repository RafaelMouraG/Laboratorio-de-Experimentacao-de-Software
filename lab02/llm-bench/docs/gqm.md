# GQM e plano de medição

Versão 0.2 — 24/09/2026. Proposta candidata, incorporando a discussão e o material das aulas. As métricas e regras abaixo serão refinadas antes da coleta. Para participantes, isolamento e pendências, consultar a [proposta de pesquisa](proposta-pesquisa.md).

Alterações da versão 0.2, a pedido de Rafael: consumo de tokens (M14) e estimativa de custo de API em M9; stack escolhida (Q8, M15); tempo de resposta da API entregue (Q9, M16). Todas são candidatas.

Decisões de Rafael de 24/09/2026, depois do [piloto com a tarefa real](piloto-tarefa-real.md): Q9 adotada, com o foco de qualidade ampliado para o desempenho da API entregue; perfil de carga de M16 adotado (§6); uma tentativa por configuração na coleta oficial (§4); aceitação sem necessidade de distinguir as configurações (§4).

## 1. Objetivo GQM

> Analisar o processo de desenvolvimento e as entregas produzidas por configurações completas de agentes de IA — modelo, harness e skills — na implementação de uma API, com o propósito de caracterizá-las e compará-las, de forma exploratória, quanto à correção funcional, robustez, manutenibilidade, eficiência e desempenho da API entregue, do ponto de vista de desenvolvedores responsáveis por revisar e utilizar as entregas, no contexto de uma tarefa controlada, com contrato HTTP previamente definido, stack livre, prazo limitado, execuções isoladas e avaliação de entregas congeladas.

| Elemento | Definição |
|---|---|
| Objeto | Processo de desenvolvimento e entregas das configurações completas |
| Propósito | Caracterizar e comparar exploratoriamente |
| Foco de qualidade | Correção funcional, robustez, manutenibilidade, eficiência e desempenho da API entregue (incluído em 24/09/2026 com a adoção de Q9) |
| Ponto de vista | Desenvolvedores que precisam revisar e utilizar as entregas |
| Contexto | Uma tarefa de API, contrato fechado, stack livre, limite de tempo e isolamento |

O limite de tempo e o contrato ainda serão definidos. A configuração é a condição comparada; uma tentativa produz uma entrega. Requisitos e resultados de testes são observações dentro de uma entrega, não repetições independentes da configuração.

## 2. Significado das dimensões

| Dimensão | Significado adotado |
|---|---|
| Correção funcional | Atendimento ao comportamento exigido pelo contrato |
| Robustez | Comportamento adequado nas entradas inválidas, limites e falhas previstos no escopo |
| Manutenibilidade | Facilidade de compreender, analisar, testar e modificar a solução; a revisão avaliará indícios dessa facilidade |
| Eficiência | Recursos necessários para produzir a entrega, interpretados em relação à qualidade obtida |

Eficiência se refere ao processo de desenvolvimento pelo agente. Desempenho da API, como latência e consumo de memória, depende de uma pergunta específica e não está implicitamente incluído. A pergunta Q9 trata do tempo de resposta. Rafael a adotou em 24/09/2026, e o foco de qualidade passou a incluir explicitamente o desempenho da API entregue, medido por M16 fora da aceitação.

A inspeção de código fornece evidências de organização, clareza e testabilidade. Medir diretamente o esforço de manutenção exigiria uma tarefa adicional de modificação, ainda não prevista. Consistência entre tentativas é uma análise transversal às quatro dimensões.

## 3. Perguntas e métricas candidatas

| Pergunta | Métricas | Evidência principal |
|---|---|---|
| Q1. A configuração produz uma entrega integralmente aceitável pelo contrato? | M1: aceitação por tentativa; M2: frequência de aceitação por configuração | Avaliação automatizada da entrega congelada |
| Q2. Quais requisitos são atendidos e onde a entrega falha? | M3: atendimento observado por requisito; M4: matriz de resultados e categorias de falha | Testes rastreáveis aos requisitos |
| Q3. Como a entrega se comporta nas condições de erro e nos limites previstos? | M5: atendimento dos requisitos de robustez, por categoria | Testes específicos derivados do contrato |
| Q4. A entrega pode ser preparada e executada a partir dos materiais fornecidos? | M6: preparação e inicialização em ambiente limpo; M7: necessidade de intervenção corretiva | Logs do avaliador e instruções entregues |
| Q5. Que recursos e assistência foram necessários para produzir a entrega? | M8: tempo por tentativa; M9: custo atribuível, observado ou estimado; M10: intervenções humanas; M14: consumo de tokens informado pelo harness | Registros de execução e consumo |
| Q6. Quanto os resultados variam entre tentativas da mesma configuração? | M11: distribuição e dispersão de aceitação, atendimento, tempo e custo | Resultados de todas as tentativas |
| Q7. Que qualidades e problemas internos relevantes existem na entrega? | M12: níveis por dimensão qualitativa; M13: divergências entre avaliações e resolução | Rubrica anonimizada com evidências e participação humana |
| Q8 (candidata). Que stack a configuração escolhe para a entrega? | M15: perfil da stack — linguagem e versão, framework HTTP, persistência, dependências diretas e forma de execução | Manifestos e arquivos da entrega congelada, instruções entregues |
| Q9 (adotada em 24/09/2026). Com que tempo a API entregue responde às requisições do contrato? | M16: latência por operação do contrato sob perfil de carga fixo, com a taxa de erros, a vazão e os recursos do servidor durante a medição | Medição do avaliador sobre a entrega congelada, em ambiente controlado |

M5 detalha requisitos já representados em M3; não constitui pontuação adicional. M11 resume medidas anteriores; não é um segundo resultado independente. M7 registra obstáculos observados na avaliação, enquanto M10 registra assistência durante a produção. M14 é insumo diagnóstico e base da estimativa de M9, e não uma medida de eficiência isolada. M15 caracteriza a entrega e não é pontuação: stacks diferentes não são ordenadas por qualidade.

## 4. Aceitação e resultados parciais

Para uma tentativa válida, propõe-se `A_i = 1` quando a entrega puder ser executada conforme exigido e todos os requisitos obrigatórios forem atendidos; caso contrário, `A_i = 0`. A definição final depende do contrato e dos critérios de aceitação.

A frequência de aceitação será `soma(A_i) / n`, em que `n` é o número de tentativas válidas segundo regras predefinidas. Mostrar sempre o numerador e o denominador, além das tentativas planejadas, iniciadas, excluídas e substituídas. Sem tentativas válidas, a medida é indefinida, não zero.

Código que não inicia, entrega incompleta e encerramento por atingir o limite da tentativa são resultados observados, e não razões automáticas para exclusão. Um defeito do avaliador que impeça a determinação do resultado exige registro de inconclusão e tratamento pelo protocolo.

Para os requisitos obrigatórios, registrar:

- `S`: satisfeitos, com evidência suficiente.
- `V`: violados, com evidência de não conformidade.
- `U`: sem resultado conclusivo.
- `N = S + V + U`: total de requisitos obrigatórios, definido antes da coleta.

M3 será o atendimento verificado `S/N`, sempre acompanhado de `S`, `V` e `U`. Quando `U > 0`, a proporção não descreve conclusivamente o comportamento dos requisitos sem evidência. Por exemplo, falha de inicialização pode determinar rejeição da entrega e ainda deixar vários requisitos de negócio sem observação.

**Decisões de 24/09/2026.**

- **Uma tentativa por configuração** na coleta oficial, por decisão de Rafael, pelo tempo disponível. Consequências:
  - M2 fica 0/1 ou 1/1 por configuração.
  - Q6 e M11 (variação entre tentativas) ficam sem dados e devem ser registrados como ausentes, não estimados.
  - Uma diferença entre configurações observada numa única tentativa não distingue efeito da configuração de variação da execução. As conclusões descrevem uma execução de cada configuração.
- **A aceitação não precisa distinguir as configurações.** Os participantes são modelos de fronteira, e a expectativa de Rafael é que todos passem. No piloto, as quatro configurações mantidas tiveram `A_i = 1`, com 35 S. A comparação se apoia então em M8, M14, M15, M16 e na revisão qualitativa (M12). `A_i` continua registrado como resultado.

O peso não será determinado pela quantidade de testes. A granularidade dos requisitos e as condições necessárias para considerar cada um satisfeito deverão ser congeladas previamente. A contagem de testes aprovados poderá aparecer como diagnóstico.

## 5. Cobertura e qualidade do instrumento de avaliação

Esta camada verifica se as evidências podem responder às perguntas da GQM. Não é uma nota do participante.

| Registro | Pergunta respondida |
|---|---|
| Requisitos com verificações definidas / total de requisitos | Existe instrumentação para cada obrigação? |
| Requisitos efetivamente exercitados / total de requisitos, por entrega | Que parte da especificação foi avaliada nesta execução? |
| Requisitos satisfeitos / total de requisitos | Que atendimento foi comprovado na entrega? |

Exemplo: dez requisitos exercitados e seis satisfeitos representam 100% de cobertura por requisito e 60% de atendimento. Ter um teste por requisito não garante cobertura suficiente dos cenários relevantes.

A matriz requisito–teste deverá identificar verificações públicas e reservadas, condições de aprovação e resultados esperados. Os casos reservados deverão ser dedutíveis da especificação entregue aos participantes. Falhas múltiplas de testes não serão automaticamente contadas como defeitos distintos no código.

## 6. Recursos, falhas e dados ausentes

Para M8, propõe-se medir o tempo decorrido entre a disponibilização do material ao agente e o congelamento da entrega por conclusão ou limite. As fronteiras exatas, incluindo instalação, espera pelo provedor e preparação do container, serão decididas no protocolo. Registrar eventos separadamente permitirá interpretar o total sem remover esperas retrospectivamente. O runner do piloto já registra horários UTC de início da tentativa, início da tarefa e término, além das durações da tarefa e total.

Para M9, distinguir custo observado de custo estimado. Registrar a fonte, unidade monetária e base de cálculo. Dados indisponíveis serão marcados como ausentes; assinaturas e consumo não atribuível não serão tratados como custo zero. Tokens e chamadas poderão ser diagnósticos, sem pressupor equivalência entre ferramentas.

A estimativa de custo de API proposta para M9 aplica, a cada categoria de tokens de M14, o preço público por token do identificador solicitado. A tabela de preços usada, sua fonte e a data de consulta ficam registradas junto do resultado. A estimativa responde "quanto custaria esta tentativa via API"; não descreve o valor efetivamente pago em assinatura nem na rota gratuita do Muse. Ela fica ausente quando faltar a contagem de alguma categoria com preço próprio ou quando o modelo não tiver preço público. Valores de custo informados pelo próprio harness serão guardados à parte, com a fonte, e não substituem a estimativa.

Para M14, registrar os tokens de entrada, saída, raciocínio e cache (leitura e escrita), separadamente e como informados por cada harness, com a fonte do dado. As ferramentas não usam a mesma semântica. No Codex, por exemplo, os tokens em cache fazem parte da entrada, enquanto no Claude Code são contados à parte. A contagem de raciocínio pode não ser exposta. Por isso, somas entre categorias e comparações diretas de tokens entre harnesses exigem normalização documentada. Categoria não informada fica ausente, não zero. Chamadas feitas por subagentes ou modelos auxiliares devem ser incluídas quando o harness as reportar e declaradas como limitação quando não reportar.

Para M15, extrair o perfil da stack dos manifestos e arquivos da entrega congelada: arquivos de dependências, Dockerfile, instruções. Os dados são nominais: linguagem, framework e persistência como categorias; dependências diretas como lista com versões. A contagem de dependências pode aparecer como diagnóstico, sem ser tratada como qualidade. Se a stack declarada nas instruções divergir da observada nos arquivos, registrar a divergência. A análise de M15 descreve escolhas e ajuda a interpretar as demais medidas, conforme a proposta (§8): diferenças de tamanho ou estrutura entre linguagens não são interpretadas automaticamente como diferenças de qualidade.

Perfil de M16 adotado em 24/09/2026: ver `rnf11_perfil_carga` em `evaluator/config.json` e a [documentação do diagnóstico](avaliador.md), §10. Em resumo:

- `DATA_DIR` em disco;
- `GET /{code}` e `POST /api/links` em duas fases: taxa fixa com latência contada do instante agendado, e concorrência 32 como saturação;
- p50 a p99.9 e máximo;
- CPU e memória do servidor;
- três medições por entrega, que estimam a variação do instrumento.

Para M16, medir somente entregas que o avaliador conseguir iniciar sem reparo (M6), no mesmo hardware, com limites de CPU e memória fixos e com a mesma persistência exigida pelo contrato. O perfil de carga define aquecimento, concorrência, duração ou número de requisições, dados iniciais e operações medidas; ele será congelado antes da coleta. Reportar percentis de latência por operação, como p50, p95 e p99, junto da taxa de erros e de respostas fora do contrato durante a medição. Latência de respostas incorretas não é tratada como desempenho válido. Entregas não iniciadas ficam sem M16, o que é registrado como ausência, sem valor atribuído. Repetições da medição sobre a mesma entrega estimam a variação do instrumento e não são novas tentativas do agente.

Para M10, registrar quantidade, tipo e duração das intervenções humanas, preservando sua finalidade. A política de assistência permitida ainda será definida.

Tempo e custo serão apresentados para todas as tentativas e, separadamente, para as aceitas, acompanhados da frequência de aceitação. Terminar rapidamente com uma entrega rejeitada não demonstra maior eficiência para produzir uma solução utilizável.

O protocolo distinguirá falhas da entrega, problemas operacionais do harness/provedor e falhas da infraestrutura experimental. Autenticação, indisponibilidade e interrupções não terão exclusão automática. Critérios de validade e substituição serão definidos antes das execuções oficiais; todas as ocorrências permanecerão no registro.

## 7. Rubrica qualitativa e escalas

Dimensões candidatas para M12:

- Clareza e facilidade de compreensão do código.
- Organização das responsabilidades e complexidade desnecessária.
- Qualidade dos testes entregues pelo participante.
- Utilidade e precisão das instruções de execução.

Os níveis ainda serão definidos com critérios observáveis e exemplos de evidência. Trataremos a rubrica como ordinal: os níveis têm ordem, mas não se presume distância constante entre eles. A proposta atual não usa média aritmética das notas nem nota global de manutenibilidade.

Apresentar avaliações por dimensão, frequências dos níveis e justificativas. Se usada uma mediana ordinal, preservar as categorias e explicitar a convenção, sem criar um nível intermediário por média numérica. Registrar os julgamentos antes da resolução das divergências. Rafael participa do julgamento final; a IA auxilia e não é o único árbitro.

| Tipo de medida | Exemplos | Tratamento proposto |
|---|---|---|
| Nominal | Categoria de falha, resultado aceito/rejeitado | Contagens e proporções por categoria |
| Ordinal | Nível da rubrica, severidade definida | Distribuição de níveis e comparações de ordem |
| Razão | Duração, custo sob base comparável, latência | Valores individuais e resumos compatíveis com distribuição e amostra |
| Contagem | Requisitos satisfeitos, intervenções, tokens por categoria | Totais com unidade e regras de contagem explícitas |

A escala não resolve, sozinha, pressupostos de independência, tamanho amostral ou comparabilidade. Não interpretar centenas de casos de teste como centenas de tentativas do agente.

## 8. Ficha operacional de cada métrica

Antes da coleta, cada métrica deverá ter uma ficha preenchida com estes campos:

| Campo | Conteúdo necessário |
|---|---|
| Identificador, nome e estado | Código estável, nome e estado de definição/congelamento |
| Objetivo e pergunta | Rastreabilidade à GQM |
| Entidade e atributo | Processo, produto ou recurso e propriedade observada |
| Unidade de observação | Tentativa, entrega, requisito, evento etc. |
| Natureza da medida | Observação direta ou derivação; relação com o atributo pretendido |
| Definição operacional | Condições exatas de coleta, regra de contagem ou fórmula |
| Escala e unidade | Categorias ou unidade quantitativa e transformações relevantes |
| Fonte e responsável | Instrumento, versão e responsável pela obtenção ou validação |
| Momento de coleta | Fronteiras temporais e artefato ao qual o dado se refere |
| Ausências e exceções | Dados indisponíveis, inconclusão, interrupção e denominador zero |
| Agregação e interpretação | Resumos previstos, sentido da comparação e limites da conclusão |
| Evidência e rastreabilidade | Referência ao log, resultado de teste ou trecho do artefato congelado |

## 9. Condições para congelar a GQM operacional

- Objetivo, perguntas e significado dos atributos revisados.
- Contrato e requisitos definidos em granularidade adequada à avaliação.
- Métricas com fichas operacionais completas e coleta viável.
- Testes rastreáveis aos requisitos e rubrica qualitativa definida.
- Regras de validade, ausência de dados, assistência e substituição estabelecidas.
- Repetições, limites e plano de análise coerentes com as conclusões pretendidas.
- Piloto concluído, com mudanças registradas antes da coleta oficial.

Essas condições ainda não foram cumpridas integralmente. A versão atual documenta a proposta e orienta as próximas decisões; não declara o experimento pronto para execução.

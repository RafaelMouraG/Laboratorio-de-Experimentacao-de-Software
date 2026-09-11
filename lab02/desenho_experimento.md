# Desenho do Experimento (Lab 02)

## 1. Hipóteses (H0 e H1)
**RQ1: O uso de assistente de IA reduz o tempo necessário para resolver uma tarefa de programação?**
* **H0:** O tempo mediano de resolução com IA é *maior ou igual* ao tempo manual ($T_{IA} \ge T_{Manual}$).
* **H1:** O tempo mediano de resolução com IA é *menor* que o tempo manual ($T_{IA} < T_{Manual}$).

**RQ2: O uso de assistente de IA reduz a quantidade de defeitos (testes que falham) no código produzido?**
* **H0:** A taxa mediana de sucesso nos testes com IA é *menor ou igual* à da codificação manual ($S_{IA} \le S_{Manual}$).
* **H1:** A taxa mediana de sucesso nos testes com IA é *maior* do que na codificação manual ($S_{IA} > S_{Manual}$).

**RQ3: O uso de assistente de IA altera a complexidade ciclomática ou a duplicação do código produzido?**
* **H0:** Não há diferença estatisticamente significativa na complexidade ciclomática mediana e na duplicação de código entre as abordagens ($C_{IA} = C_{Manual}$).
* **H1:** Há diferença estatisticamente significativa na complexidade ciclomática mediana e/ou na duplicação de código entre as abordagens ($C_{IA} \ne C_{Manual}$).

## 2. Variáveis Dependentes e Independentes
* **Variável Independente (VI):** Uso de assistente de IA (Níveis: Com IA vs. Sem IA / Manual).
* **Variáveis Dependentes (VD):**
  * **VD1 (RQ1):** Tempo de resolução "time-to-green" (minutos). Limitado a 35 min (censurado em caso de falha).
  * **VD2 (RQ2):** Taxa de sucesso (% de testes de aceitação passando).
  * **VD3 (RQ3):** Complexidade ciclomática e Porcentagem de código duplicado, controladas por LOC.

## 3. Tratamentos
* **Tratamento 1 (Controle):** Codificação manual. O programador resolve o kata com a IDE, sem IA
  generativa — extensões de assistência por IA (autocompletar inline, chat na IDE) **desabilitadas**
  antes do trial. Consulta permitida apenas à documentação oficial da linguagem.
* **Tratamento 2 (Experimental):** Codificação com assistente de IA. O programador resolve o kata
  utilizando o **Claude (Anthropic)** — o mesmo assistente em todos os trials do grupo, conforme o
  Passo 2 do enunciado, para que o tratamento seja comparável dentro do experimento.

**Modelo e interface — a fixar antes do primeiro trial da S02.** A família do assistente está decidida
(Claude); o **modelo** (ex.: `claude-opus-5`, `claude-sonnet-5`) e a **interface** (Claude Code no
terminal, claude.ai no navegador, extensão de IDE) ainda não. Ambos precisam ser escolhidos **antes**
do primeiro trial e mantidos idênticos nos 6 trials com IA: trocar de modelo ou de interface no meio
da execução transforma o Tratamento 2 em dois tratamentos diferentes e inviabiliza a comparação. A
interface pesa tanto quanto o modelo — conversar no chat e copiar código não é o mesmo esforço que ter
o agente editando os arquivos do kata direto.

**Registro obrigatório para reprodução (Passo 5):** modelo, interface e data de execução de cada trial
ficam registrados no Relatório Final. Assistentes evoluem entre versões, e sem esse registro o
experimento não é replicável — ver §7.3.

## 4. Objetos Experimentais (Katas)
Quatro katas autorais em **Python 3**, escritos pelo grupo, cada um com sua suíte de testes de
aceitação em `pytest` (ver [`katas/README.md`](katas/README.md) e `katas/k1..k4/enunciado.md`):

| Kata | Tema | Núcleo algorítmico |
| :--- | :--- | :--- |
| **K1** | Telemetria de drones | Parsing de strings, agrupamento em dicionário, desempate sequencial |
| **K2** | Agrupamento de lotes | Ordenação + estratégia gulosa com dois ponteiros |
| **K3** | Validador de código de barras | Iteração e fatiamento de strings, condições lógicas compostas |
| **K4** | Distância de rotas | Ordenação de tuplas + união de intervalos sobrepostos |

**Equivalência de dificuldade:** as quatro soluções de referência ficam entre 10 e 20 linhas de
Python, com complexidade ciclomática projetada entre 3 e 5 por função, sem bibliotecas externas nem
estruturas de dados avançadas. O piloto de resolução manual levou entre 12 e 20 minutos, dentro do
time-box de 35 min — margem que reduz a expectativa de trials censurados. A justificativa completa
está em [`katas/README.md`](katas/README.md).

**Baixa indexação:** os katas reaproveitam lógicas algorítmicas clássicas, mas com narrativa e
semântica de dados inteiramente reescritas e com restrições secundárias próprias (regras de
precedência no K1, dígitos crescentes no K3), para que o assistente tenha de interpretar e adaptar em
vez de recuperar uma solução vista em treinamento.

## 5. Projeto Crossover Within-Subject Contrabalanceado
O experimento utiliza um desenho *within-subject* (todos testam ambos os tratamentos), em formato *crossover* (alternando tratamentos) e *contrabalanceado* (variando a ordem entre integrantes para mitigar efeito de aprendizado/cansaço).

### Tabela de Ordem (3 Integrantes, 4 Katas)
| Integrante | K1 | K2 | K3 | K4 |
| :--- | :--- | :--- | :--- | :--- |
| **Integrante A** | Com IA | Sem IA | Com IA | Sem IA |
| **Integrante B** | Sem IA | Com IA | Sem IA | Com IA |
| **Integrante C** | Com IA | Com IA | Sem IA | Sem IA |

*(O planejamento da execução de cada trial, além da criação do template oficial de planilha para coleta das métricas na Sprint 2, é gerado de forma automatizada pelo script `gerar_tabela_contrabalanceamento.py` (que consolida os dados no arquivo `template_coleta_dados_s02.csv`) disponibilizado neste repositório).*

## 6. Número de Medições
* Integrantes: 3
* Katas: 4
* **Total:** 12 medições (6 com IA, 6 sem IA).

## 7. Ameaças à Validade
As ameaças abaixo são as que consideramos relevantes para este desenho, com a mitigação já embutida no
experimento e o risco residual que permanece — este último deve ser retomado como limitação no
Relatório Final (Passo 5).

### 7.1 Validade Interna
* **Efeito de aprendizado / maturação entre katas.** Resolver katas em sequência melhora o desempenho
  nos últimos independentemente do tratamento.
  *Mitigação:* desenho crossover contrabalanceado (§5), que distribui as posições 1–4 entre os dois
  tratamentos; os quatro katas usam núcleos algorítmicos distintos (§4), reduzindo transferência
  direta de raciocínio; a ordem é fixada antes da execução e não pode ser trocada durante a S02.
  *Risco residual:* com 3 integrantes o contrabalanceamento é incompleto — o Integrante C executa os
  dois trials com IA antes dos dois manuais, concentrando o aprendizado no tratamento manual.
* **Vazamento de solução já vista (carry-over).** Ter resolvido um kata com IA facilitaria refazê-lo
  manualmente.
  *Mitigação:* cada par integrante × kata ocorre em **um único** tratamento (§5) — nenhum integrante
  resolve o mesmo kata duas vezes, portanto não há reaproveitamento da própria solução.
  *Risco residual:* comunicação entre integrantes. Os trials são individuais e os katas não devem ser
  discutidos entre o trio até o encerramento da S02.
* **Contaminação do tratamento de controle.** Autocompletar baseado em IA (Copilot inline, sugestões
  da IDE) torna o trial "sem IA" um tratamento intermediário, não um controle.
  *Mitigação:* extensões de IA generativa desabilitadas na IDE antes de cada trial manual; consulta
  permitida apenas à documentação oficial da linguagem, registrada no relatório como política fixa.
  *Risco residual:* depende de disciplina do próprio integrante, sem verificação automática.
* **Familiaridade prévia com a ferramenta de IA.** Um integrante que já usa o assistente diariamente
  extrai mais dele do que quem o usa pela primeira vez, e o efeito medido passa a misturar "efeito da
  IA" com "efeito de saber operar a IA".
  *Mitigação:* o grupo usa o **mesmo assistente (Claude), na mesma versão**, em todos os trials, com o
  modelo e a interface exatos registrados conforme o §3; o nível de experiência prévia de cada
  integrante com o Claude é declarado no relatório.
  *Risco residual:* não é controlável com 3 sujeitos — permanece como fator de confusão declarado.
* **Fadiga e efeito de horário.** Quatro trials de até 35 min seguidos degradam o desempenho nos
  últimos.
  *Mitigação:* no máximo dois trials por sessão, com intervalo mínimo de 10 minutos entre eles.
* **Pesquisadores como sujeitos (viés de expectativa).** Os três integrantes conhecem as hipóteses e
  são os próprios sujeitos, o que pode enviesar o esforço aplicado em cada tratamento.
  *Mitigação:* o desfecho é objetivo e automatizado — o critério de parada é a suíte de aceitação
  passando, e tempo e testes são gravados pelo script de cronometragem (`src/cronometragem.py`), não
  anotados à mão.
* **Instrumentação.** O cronômetro roda a suíte em intervalos regulares, o que adiciona overhead e
  limita a granularidade do `tempo_s` ao período de verificação.
  *Mitigação:* a mesma instrumentação e o mesmo intervalo valem para os dois tratamentos, tornando o
  viés simétrico e sem efeito sobre a comparação.

### 7.2 Validade de Construto
* **Tempo como medida de produtividade.** O `time-to-green` captura apenas a velocidade até a primeira
  versão correta; ignora esforço de revisão, legibilidade e manutenção posterior.
* **Testes de aceitação como medida de defeitos.** A `taxa_sucesso` só enxerga os defeitos que a suíte
  cobre. As suítes vêm prontas com o kata e são idênticas nos dois tratamentos, o que preserva a
  comparação, mas subestima defeitos não cobertos (validação de entrada, casos de borda não testados).
* **Métricas estáticas como medida de qualidade estrutural.** Em soluções de 10–20 linhas a
  complexidade ciclomática tem faixa de variação estreita (3–5 projetado), com pouca sensibilidade
  para diferenciar tratamentos; e `duplicacao_pct` depende do limiar adotado (`--min-lines 5
  --min-tokens 30`), abaixo do padrão do `jscpd`. `loc` é reportado obrigatoriamente junto de
  `cc_media` e `duplicacao_pct`, porque código gerado por IA tende a ser mais verboso e as duas
  métricas sem normalização por tamanho enganam.
* **Censura no time-box.** Trials que atingem 35 min sem green entram como `tempo_s = 2100` com
  `censurado_35min = true`. Isso comprime a cauda: o tempo real que o integrante levaria é maior que
  2100, então a diferença entre tratamentos é **subestimada**, nunca inflada. Descartá-los seria pior
  (favoreceria o tratamento com mais falhas), e por isso não são descartados. O número de censurados
  por tratamento é reportado junto das medianas.

### 7.3 Validade Externa
* **Sujeitos:** 3 estudantes de graduação do mesmo curso e período, não amostrados aleatoriamente. Os
  resultados não se generalizam para desenvolvedores profissionais.
* **Tarefas:** katas de 10–20 linhas, sem código legado, build, integração ou revisão por pares — o
  cenário em que assistentes de IA são de fato usados no dia a dia. Ganhos em katas não se transferem
  automaticamente para bases de código reais.
* **Tecnologia:** um único assistente, em uma única versão, e uma única linguagem (Python, escolhida
  por causa do Radon). Assistentes evoluem rápido, o que limita a validade temporal do resultado — daí
  o registro da versão exata no relatório.

### 7.4 Validade de Conclusão (estatística)
* **Poder estatístico baixo.** São 12 medições (6 por tratamento). O teste de Wilcoxon pareado com
  esse N detecta apenas efeitos grandes: um resultado não significativo **não** é evidência de
  ausência de efeito. Reportar, além do p-valor, o tamanho do efeito e as medianas com IQR.
* **Definição do pareamento.** O desenho não produz pares kata × integrante nos dois tratamentos
  (§7.1), logo o pareamento do Wilcoxon precisa ser declarado explicitamente na análise (Passo 4) —
  por integrante, agregando seus trials de cada tratamento, o que reduz o N pareado a 3. A alternativa
  não pareada perde o controle da variação individual de habilidade, que é justamente o motivo do
  desenho within-subject.
* **Dificuldade do kata como fator de confusão.** Cada kata aparece em proporções desiguais entre os
  tratamentos (K1 e K2: 2 com IA e 1 sem; K3 e K4: o inverso), então parte da diferença observada pode
  vir do kata, não do tratamento. Reportar também os resultados por kata.
* **Múltiplas comparações.** São três RQs e, na RQ3, quatro métricas (`cc_media`, `duplicacao_pct`,
  `mi`, `loc`), o que infla a chance de um falso positivo. A RQ3 é tratada como **exploratória**, sem
  afirmação de significância isolada por métrica.

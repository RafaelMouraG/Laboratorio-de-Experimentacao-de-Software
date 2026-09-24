# Mini benchmark exploratório de agentes de programação

Proposta de pesquisa para comparar configurações completas de agentes de IA — modelo, harness e skills — no desenvolvimento de uma API. Este projeto é complementar ao **lab02 obrigatório**, que permanece separado.

**Estado em 24/09/2026:** proposta em elaboração. A GQM orientará a definição do enunciado, dos requisitos, dos critérios de avaliação, do protocolo e dos testes. A coleta oficial ainda não começou.

## Documentação

- [Proposta de pesquisa](docs/proposta-pesquisa.md): contexto, participantes pretendidos, isolamento, avaliação, decisões em aberto e contribuições do material das aulas.
- [GQM e plano de medição](docs/gqm.md): objetivo, perguntas, métricas candidatas, regras de interpretação e ficha operacional de medição.
- [Verificação inicial do ambiente](docs/verificacao-ambiente.md): versões, estado de autenticação no host, identificadores encontrados e checagem básica de isolamento.
- [Contrato candidato do encurtador](docs/contrato-encurtador.md): enunciado, requisitos com verificação e decisões pendentes. Documento privado; somente a Parte A se destina aos participantes.
- [Piloto de infraestrutura](docs/piloto-infraestrutura.md): tentativas sintéticas nos containers, resultados por participante e pendências. O ambiente está em [infra/pilot](infra/pilot/README.md).
- [Imagem multi-linguagem](infra/runtime/README.md): ambiente candidato da coleta, com Python, Node, Go e Java, e o resultado da validação.
- [Avaliador do encurtador](docs/avaliador.md): verificação automatizada dos 35 requisitos de aceitação sobre uma entrega congelada, com implementação de referência e controles. Documento privado. O código está em `evaluator/`.
- [Runner da coleta](infra/attempt/README.md): uma tentativa da tarefa real por execução, com congelamento da entrega e avaliação em ambiente limpo. Validado sem modelo; nenhuma tentativa real executada.

O encurtador de URL é a tarefa candidata, com stack livre e contrato HTTP a definir. Identificadores foram encontrados em catálogos e fontes oficiais; as configurações finais e o acesso aos modelos dentro dos containers ainda precisam de validação antes da coleta.

O repositório central deverá permanecer privado durante a coleta. Participantes receberão somente os materiais de sua própria tentativa. Esta documentação de coordenação não deve ser disponibilizada integralmente aos participantes.

## Próxima etapa

Concluir o piloto de infraestrutura: executar o Sol, que também valida a extração de tokens no formato do Codex. Gemini foi substituído por MiMo-V2.6-Flash Free, que depois também foi retirado, após duas entregas vazias no [piloto com a tarefa real](docs/piloto-tarefa-real.md). A coleta tem quatro participantes: Opus, Sol, Astra e Muse. O Astra foi incluído depois do piloto com a tarefa real. Em paralelo, refinar as subperguntas e definições operacionais da GQM e depois fechar o escopo e os critérios de avaliação. O avaliador e o runner da coleta estão prontos em versão provisória. O piloto com a tarefa real ([registro](docs/piloto-tarefa-real.md)) teve uma entrega aceita de cada participante: Opus, Sol, Astra e Muse. O Sol precisou de uma correção da imagem. O próximo passo é decidir os parâmetros `[A DEFINIR]` e o perfil de carga do RNF11 com base nesses dados, e fixar os binários dos harnesses antes de congelar a imagem.

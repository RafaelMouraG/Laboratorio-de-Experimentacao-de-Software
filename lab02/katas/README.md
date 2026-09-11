# Katas da S02

Este documento registra a escolha e a avaliação prévia dos quatro katas elaborados para o experimento do Laboratório 02. O propósito do experimento é avaliar se a utilização de assistentes de IA afeta o tempo de desenvolvimento e a qualidade estrutural do código. Para garantir a validade dos resultados e evitar vieses experimentais, é essencial que os exercícios apresentem o mesmo nível de dificuldade.

## Descrição dos Katas

- **K1 (Log de Drones)**: Requer manipulação de strings (separação de campos via `split`), uso de dicionários para agrupamento/contagem e ordenação baseada em regras de desempate sequencial.
- **K2 (Agrupamento de Lotes)**: Exige a ordenação prévia da coleção e a implementação de uma lógica gulosa (*greedy*) utilizando a técnica de dois ponteiros (*two pointers*) para otimizar o empacotamento.
- **K3 (Validador de Código de Barras)**: Foca na iteração e no fatiamento (*slicing*) de strings, exigindo a validação de condições lógicas compostas que envolvem a verificação de valores numéricos e alfabéticos da tabela ASCII.
- **K4 (Distância de Rotas)**: Envolve a ordenação de tuplas e a construção de um algoritmo para unificar intervalos numéricos sobrepostos (*merge intervals*).

## Justificativa de Equivalência

1. **Esforço Algorítmico**: Os quatro exercícios demandam laços de repetição simples sobre uma coleção fundamental (lista ou string) e podem ser solucionados com 10 a 20 linhas de código em Python. Não há a necessidade de importar bibliotecas complexas ou construir estruturas de dados avançadas, como árvores e grafos. A complexidade ciclomática projetada para as soluções de referência situa-se entre 3 e 5 por função.
2. **Tempo de Resolução**: A simulação da resolução dos quatro problemas, sem o auxílio de IA, resultou em tempos médios que variam entre 12 e 20 minutos. Isso assegura que as tarefas cabem confortavelmente no time-box restrito de 35 minutos estabelecido para o laboratório, evitando altas taxas de dados censurados por esgotamento de tempo. Com o suporte de IA, o tempo estimado de resolução é reduzido para menos de 5 minutos.
3. **Resiliência contra Memorização**: Para evitar que os modelos de IA forneçam a resposta instantaneamente a partir da sua base de treinamento original, adaptamos lógicas algorítmicas tradicionais (frequentemente encontradas em plataformas de juiz online), mas modificamos por completo a narrativa e a semântica dos dados. Adicionalmente, inserimos restrições secundárias como a limitação de dígitos crescentes no K3 e as regras de precedência no K1 para forçar o LLM a interpretar e adaptar a solução analiticamente em vez de apenas resgatá-la da memória.

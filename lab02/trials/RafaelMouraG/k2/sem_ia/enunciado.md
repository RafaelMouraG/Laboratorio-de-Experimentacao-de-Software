# Kata 2: Agrupamento de Lotes para Envio

Dada uma lista de tamanhos de arquivos (em MB), o objetivo é agrupá-los em lotes para otimizar o envio por uma rede. Cada lote possui uma capacidade máxima permitida.

Você deve implementar a função `minimos_lotes(tamanhos, capacidade)` no arquivo `k2.py`. A função deve calcular e retornar o menor número de lotes necessários para enviar todos os arquivos.

As restrições são as seguintes:
- Um lote pode conter no máximo 2 arquivos.
- A soma dos tamanhos dos arquivos em um lote não pode exceder a capacidade máxima estipulada.

(Considere que nenhum arquivo individualmente será maior do que a capacidade do lote).

### Exemplo 1
```python
tamanhos = [1, 2]
capacidade = 3
# Retorna 1, pois os dois arquivos podem ser alocados juntos no mesmo lote.
```

### Exemplo 2
```python
tamanhos = [3, 2, 2, 1]
capacidade = 3
# Retorna 3
# Lote 1: [3]
# Lote 2: [2, 1]
# Lote 3: [2]
```

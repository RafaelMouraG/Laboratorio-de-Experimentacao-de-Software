# Kata 4: Consolidação de Rotas de Entrega

Neste exercício, trabalharemos com a consolidação de intervalos. Considere uma lista de tuplas `(km_inicio, km_fim)` que representam os trechos de uma rodovia percorridos por um caminhão de entrega.

A transportadora precisa determinar a distância total única percorrida pelo veículo. Isso significa que, se o caminhão passar por um mesmo trecho múltiplas vezes, a quilometragem desse trecho deve ser contabilizada apenas uma vez na distância total.

Implemente a função `consolidar_rotas(rotas)` no arquivo `k4.py`. A função recebe a lista de tuplas (que podem não estar ordenadas) e deve retornar a distância total consolidada.

### Exemplo 1
```python
rotas = [(10, 20), (30, 40)]
# Retorna 20
# Os trechos são independentes. 20-10 = 10, e 40-30 = 10. A soma total é 20.
```

### Exemplo 2
```python
rotas = [(10, 50), (20, 60)]
# Retorna 50
# Os trechos se sobrepõem. Ao unificá-los, obtemos o intervalo do 10 ao 60, totalizando uma distância de 50.
```

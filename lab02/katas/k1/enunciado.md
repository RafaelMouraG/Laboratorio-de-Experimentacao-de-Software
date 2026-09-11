# Kata 1: Análise de Telemetria de Drones

Neste exercício, propomos a análise de logs de telemetria de uma frota de drones. 
A entrada fornecida é uma lista de strings no formato `"ID_DO_DRONE;BATERIA;TEMPERATURA;STATUS"`.

O objetivo é identificar qual drone apresentou a maior quantidade de falhas, ou seja, aquele com o maior número de logs marcados com o status `"ERROR"`.
Caso ocorra um empate entre dois ou mais drones, você deve retornar o drone cuja primeira falha foi registrada antes na lista.
Se a lista estiver vazia ou não contiver nenhum erro, a função deve retornar `"NENHUM_ERRO"`.

Implemente a função `analisar_telemetria(logs)` no arquivo `k1.py`.

### Exemplo 1
```python
logs = [
    "D01;90;40;OK",
    "D02;30;45;ERROR",
    "D01;85;41;ERROR",
    "D02;25;48;ERROR"
]
# Retorna "D02" (apresentou 2 erros)
```

### Exemplo 2
```python
logs = [
    "D04;90;40;OK",
    "D05;30;45;ERROR",
    "D06;85;41;ERROR",
    "D05;25;48;ERROR",
    "D06;80;42;ERROR"
]
# Retorna "D05" (empatou com o D06 com 2 erros cada, mas a primeira falha do D05 ocorreu antes)
```

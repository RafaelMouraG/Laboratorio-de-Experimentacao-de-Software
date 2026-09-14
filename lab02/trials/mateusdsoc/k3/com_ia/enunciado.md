# Kata 3: Validador de Códigos de Barras

O propósito deste exercício é validar strings que representam códigos de barras industriais. Para que um código seja considerado válido, ele deve atender a todas as cinco regras abaixo:

1. Possuir exatamente 12 caracteres.
2. Iniciar com um dígito numérico.
3. Terminar com uma letra.
4. Não possuir 3 caracteres idênticos em sequência (por exemplo, `"AAA"` ou `"111"` invalidam a string).
5. Não possuir 3 dígitos numéricos em sequência crescente (por exemplo, `"123"` ou `"456"` invalidam a string). Observação: essa regra se aplica exclusivamente a números; letras em ordem alfabética são permitidas.

Implemente a função `validar_codigo_barras(codigo)` no arquivo `k3.py`. A função deve retornar `True` caso o código seja válido e `False` caso contrário.

### Exemplo 1
```python
validar_codigo_barras("5A8g910Bjk1A")
# Retorna True. O código atende a todas as regras estabelecidas.
```

### Exemplo 2
```python
validar_codigo_barras("5A8g910Bjk11")
# Retorna False. Viola a regra 3, pois termina com um número.
```

### Exemplo 3
```python
validar_codigo_barras("8B234KLM901a")
# Retorna False. Viola a regra 5, pois contém a sequência crescente de dígitos "234".
```

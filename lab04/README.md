# Lab04: Testes de Hipótese por Dentro

Comparamos o t de Welch e o Mann-Whitney no tempo até o merge de PRs, com e sem bot de revisão. Os
dados reais calibram a simulação e, como somos nós que geramos os dados simulados, dá para medir
quantas vezes cada teste acerta ou erra.

- **Board:** https://github.com/users/RafaelMouraG/projects/12

> Setup do ambiente (`.env`, `.venv`, dependências) está no [README da raiz](../README.md).

## Como rodar

Da raiz do repositório:

```bash
python -m lab04
```

O comando roda tudo, com semente fixa, e grava o dashboard em `lab04/dashboard/index.html`, que abre
direto no navegador. Esse HTML é gerado, por isso fica fora do git.

## Pastas

| Pasta | O que guarda |
|---|---|
| `data/` | Os PRs coletados, em CSV, e o script da coleta |
| `simulacao/` | Gerador dos dados simulados, os dois testes e o motor das repetições |
| `dashboard/` | Código que monta a página |
| `tests/` | Testes, com `pytest lab04/tests` |

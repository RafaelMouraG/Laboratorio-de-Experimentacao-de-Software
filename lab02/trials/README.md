# Código final dos trials

Um diretório por trial, no layout que o runner de métricas estáticas (Issue #41) varre:

```
lab02/trials/<integrante>/<kata>/<com_ia|sem_ia>/
```

Exemplo:

```
lab02/trials/
  mateusdsoc/
    k1/
      com_ia/     solucao.py, test_k1.py
      sem_ia/     solucao.py, test_k1.py
```

**Arquive o código aqui ao fim de cada trial**, antes de começar o próximo. Sem isso o trial
seguinte sobrescreve o diretório de trabalho e a medição da RQ3 do trial anterior se perde — e o
código final é o insumo da RQ3, não dá para recuperar depois.

O que entra na medição: só o código escrito no trial. Os testes de aceitação vêm prontos com o kata,
então `test_*.py`, `*_test.py`, `conftest.py` e diretórios `tests/` são ignorados pelo script — pode
deixá-los aqui à vontade, junto da solução, que não contaminam `cc_media`, `loc`, `mi` nem
`duplicacao_pct`.

Depois de arquivar tudo, uma passada só preenche as colunas da RQ3 de todos os trials:

```bash
python lab02/src/metricas_estaticas.py --lote
```

import pytest
from k2 import minimos_lotes

def test_lote_vazio():
    assert minimos_lotes([], 5) == 0

def test_um_arquivo():
    assert minimos_lotes([3], 5) == 1

def test_dois_arquivos_cabem():
    assert minimos_lotes([1, 2], 3) == 1

def test_dois_arquivos_nao_cabem():
    assert minimos_lotes([2, 2], 3) == 2

def test_exemplo_enunciado_1():
    assert minimos_lotes([3, 2, 2, 1], 3) == 3

def test_exemplo_enunciado_2():
    assert minimos_lotes([3, 5, 3, 4], 5) == 4

def test_arquivos_pequenos():
    assert minimos_lotes([1, 1, 1, 1], 2) == 2

def test_ordem_embaralhada():
    assert minimos_lotes([4, 1, 3, 2], 5) == 2

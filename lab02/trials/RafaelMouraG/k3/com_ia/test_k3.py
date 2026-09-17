import pytest
from k3 import validar_codigo_barras

def test_tamanho_invalido():
    assert not validar_codigo_barras("1A")
    assert not validar_codigo_barras("1A2B3C4D5E6F7G")

def test_inicia_letra():
    assert not validar_codigo_barras("A1234567890B")

def test_termina_digito():
    assert not validar_codigo_barras("1A2B3C4D5E61")

def test_3_caracteres_iguais():
    assert not validar_codigo_barras("1AAAB3C4D5EB")
    assert not validar_codigo_barras("1A2B333D5E6B")

def test_3_digitos_crescentes():
    assert not validar_codigo_barras("1A2B345D5E6B")
    assert not validar_codigo_barras("789B3C4D5E6B")
    assert not validar_codigo_barras("1A2B3C4D5123")
    
def test_valido():
    assert validar_codigo_barras("5A8g910Bjk1A")
    assert validar_codigo_barras("1A2B3C4D5E6F")
    
def test_digitos_crescentes_letras_juntas_permitidas():
    assert validar_codigo_barras("1ABCDEFGH12Z")

import pytest
from k4 import consolidar_rotas

def test_lista_vazia():
    assert consolidar_rotas([]) == 0

def test_um_intervalo():
    assert consolidar_rotas([(5, 10)]) == 5

def test_intervalos_disjuntos():
    assert consolidar_rotas([(10, 20), (30, 40)]) == 20

def test_intervalos_sobrepostos():
    assert consolidar_rotas([(10, 50), (20, 60)]) == 50

def test_intervalos_contidos():
    assert consolidar_rotas([(10, 100), (20, 50), (60, 80)]) == 90

def test_exemplo_complexo():
    assert consolidar_rotas([(100, 120), (110, 130), (150, 160), (90, 115)]) == 50

def test_adjacentes():
    assert consolidar_rotas([(10, 20), (20, 30)]) == 20

def test_ordem_completamente_aleatoria():
    assert consolidar_rotas([(50, 60), (10, 30), (20, 40)]) == 40

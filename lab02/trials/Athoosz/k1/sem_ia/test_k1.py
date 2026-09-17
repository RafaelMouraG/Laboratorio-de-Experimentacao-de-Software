import pytest
from k1 import analisar_telemetria

def test_nenhum_erro():
    logs = [
        "D01;90;40;OK",
        "D02;30;45;WARNING"
    ]
    assert analisar_telemetria(logs) == "NENHUM_ERRO"

def test_lista_vazia():
    assert analisar_telemetria([]) == "NENHUM_ERRO"

def test_um_erro_simples():
    logs = [
        "D01;90;40;OK",
        "D02;30;45;ERROR",
        "D01;85;41;WARNING"
    ]
    assert analisar_telemetria(logs) == "D02"

def test_multiplos_erros_desempate_quantidade():
    logs = [
        "D01;90;40;OK",
        "D02;30;45;ERROR",
        "D01;85;41;ERROR",
        "D02;25;48;ERROR"
    ]
    assert analisar_telemetria(logs) == "D02"

def test_empate_retorna_primeiro_a_falhar():
    logs = [
        "D04;90;40;OK",
        "D05;30;45;ERROR", 
        "D06;85;41;ERROR",
        "D05;25;48;ERROR",
        "D06;80;42;ERROR"  
    ]
    assert analisar_telemetria(logs) == "D05"

def test_empate_retorna_primeiro_ordem_invertida():
    logs = [
        "D06;85;41;ERROR",
        "D05;30;45;ERROR",
        "D05;25;48;ERROR",
        "D06;80;42;ERROR"
    ]
    assert analisar_telemetria(logs) == "D06"

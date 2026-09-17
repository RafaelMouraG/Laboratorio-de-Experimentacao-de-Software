def analisar_telemetria(logs: list[str]) -> str:
    """
    Dada uma lista de logs no formato "ID_DO_DRONE;BATERIA;TEMPERATURA;STATUS",
    retorna o ID do drone que apresentou a maior quantidade de falhas (status "ERROR").
    Em caso de empate, retorna o que registrou a falha antes na lista.
    Caso nenhum erro seja encontrado, retorna "NENHUM_ERRO".
    """
    contagem_erros = {}
    
    if len(logs) == 0:
        return "NENHUM_ERRO"

    for linha in logs:
        partes = linha.split(";")

        id_drone = partes[0]
        status = partes[3]

        if status == "ERROR":
            if id_drone in contagem_erros:
                contagem_erros[id_drone] = contagem_erros[id_drone] + 1
            else:
                contagem_erros[id_drone] = 1

    if len(contagem_erros) == 0:
        return "NENHUM_ERRO"

    max_erros = -1
    pior_drone = ""

    for drone in contagem_erros:
        erros_desse_drone = contagem_erros[drone]
        
        if erros_desse_drone > max_erros:
            max_erros = erros_desse_drone
            pior_drone = drone

    return pior_drone
        
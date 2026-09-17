def analisar_telemetria(logs: list[str]) -> str:
    """
    Dada uma lista de logs no formato "ID_DO_DRONE;BATERIA;TEMPERATURA;STATUS",
    retorna o ID do drone que apresentou a maior quantidade de falhas (status "ERROR").
    Em caso de empate, retorna o que registrou a falha antes na lista.
    Caso nenhum erro seja encontrado, retorna "NENHUM_ERRO".
    """
    contagem = {}
    primeira_falha = {}
    for indice, log in enumerate(logs):
        drone_id, _bateria, _temperatura, status = log.split(";")
        if status == "ERROR":
            contagem[drone_id] = contagem.get(drone_id, 0) + 1
            primeira_falha.setdefault(drone_id, indice)

    if not contagem:
        return "NENHUM_ERRO"

    return min(contagem, key=lambda d: (-contagem[d], primeira_falha[d]))

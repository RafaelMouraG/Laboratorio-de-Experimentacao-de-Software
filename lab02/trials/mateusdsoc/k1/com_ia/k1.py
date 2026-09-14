def analisar_telemetria(logs: list[str]) -> str:
    """
    Dada uma lista de logs no formato "ID_DO_DRONE;BATERIA;TEMPERATURA;STATUS",
    retorna o ID do drone que apresentou a maior quantidade de falhas (status "ERROR").
    Em caso de empate, retorna o que registrou a falha antes na lista.
    Caso nenhum erro seja encontrado, retorna "NENHUM_ERRO".
    """
    contagem_erros = {}
    primeira_falha = {}

    for indice, log in enumerate(logs):
        drone_id, _bateria, _temperatura, status = log.split(";")
        if status != "ERROR":
            continue
        contagem_erros[drone_id] = contagem_erros.get(drone_id, 0) + 1
        if drone_id not in primeira_falha:
            primeira_falha[drone_id] = indice

    if not contagem_erros:
        return "NENHUM_ERRO"

    return max(
        contagem_erros,
        key=lambda drone_id: (contagem_erros[drone_id], -primeira_falha[drone_id]),
    )

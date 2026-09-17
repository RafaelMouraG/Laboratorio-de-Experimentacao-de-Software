def consolidar_rotas(rotas: list[tuple[int, int]]) -> int:
    """
    Dada uma lista de rotas de entrega (km_inicio, km_fim),
    retorna a distância total única percorrida, sem contabilizar trechos sobrepostos.
    """
    if not rotas:
        return 0

    # Ordenar por km_inicio deixa os trechos que podem se fundir lado a lado:
    # qualquer sobreposição acontece com o trecho que vem logo depois.
    ordenadas = sorted(rotas)
    inicio, fim = ordenadas[0]
    total = 0

    for km_inicio, km_fim in ordenadas[1:]:
        if km_inicio <= fim:
            # Encosta ou invade o trecho atual: estende o fim (o max cobre o caso
            # de um intervalo totalmente contido no outro).
            fim = max(fim, km_fim)
        else:
            # Abre um trecho novo: fecha o atual e soma o que ele cobre.
            total += fim - inicio
            inicio, fim = km_inicio, km_fim

    return total + (fim - inicio)

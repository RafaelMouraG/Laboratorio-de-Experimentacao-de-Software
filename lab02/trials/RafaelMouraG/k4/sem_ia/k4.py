def consolidar_rotas(rotas: list[tuple[int, int]]) -> int:
    """
    Dada uma lista de rotas de entrega (km_inicio, km_fim),
    retorna a distância total única percorrida, sem contabilizar trechos sobrepostos.
    """
    if not rotas:
        return 0

    rotas = sorted(rotas)

    inicioAtual, fimAtual = rotas[0]
    distanciaTotal = 0

    for inicio, fim in rotas[1:]:
        if inicio <= fimAtual:
            fimAtual = max(fimAtual, fim)
        else:
            distanciaTotal += fimAtual - inicioAtual
            inicioAtual = inicio
            fimAtual = fim

    distanciaTotal += fimAtual - inicioAtual

    return distanciaTotal
def consolidar_rotas(rotas: list[tuple[int, int]]) -> int:
    """
    Dada uma lista de rotas de entrega (km_inicio, km_fim),
    retorna a distância total única percorrida, sem contabilizar trechos sobrepostos.
    """
    total = 0
    alcance = 0

    for inicio, fim in sorted(rotas):
        total += max(0, fim - max(inicio, alcance))
        alcance = max(alcance, fim)

    return total
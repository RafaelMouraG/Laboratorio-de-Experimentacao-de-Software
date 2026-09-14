def minimos_lotes(tamanhos: list[int], capacidade: int) -> int:
    """
    Dada uma lista de tamanhos de arquivos e uma capacidade máxima de lote,
    retorna o número mínimo de lotes necessários para enviar todos os arquivos.

    Restrições:
    - Um lote pode conter no máximo 2 arquivos.
    - A soma dos tamanhos não pode exceder a capacidade máxima estipulada.
    """
    arquivos = sorted(tamanhos)
    i, j = 0, len(arquivos) - 1
    lotes = 0

    while i <= j:
        if arquivos[i] + arquivos[j] <= capacidade:
            i += 1
        j -= 1
        lotes += 1

    return lotes
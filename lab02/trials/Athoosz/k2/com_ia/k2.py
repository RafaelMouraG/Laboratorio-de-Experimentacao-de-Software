def minimos_lotes(tamanhos: list[int], capacidade: int) -> int:
    """
    Dada uma lista de tamanhos de arquivos e uma capacidade máxima de lote,
    retorna o número mínimo de lotes necessários para enviar todos os arquivos.
    Restrições:
    - Um lote pode conter no máximo 2 arquivos.
    - A soma dos tamanhos não pode exceder a capacidade máxima estipulada.
    """
    ordenados = sorted(tamanhos)
    esquerda, direita = 0, len(ordenados) - 1
    lotes = 0

    while esquerda <= direita:
        # O maior arquivo restante ocupa um lote de qualquer forma. Se o menor
        # ainda couber junto dele, vale aproveitar a vaga: é o par mais barato
        # possível, e nenhuma outra combinação sobraria para o menor.
        if esquerda < direita and ordenados[esquerda] + ordenados[direita] <= capacidade:
            esquerda += 1
        direita -= 1
        lotes += 1

    return lotes

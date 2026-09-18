def minimos_lotes(tamanhos: list[int], capacidade: int) -> int:
    """
    Dada uma lista de tamanhos de arquivos e uma capacidade máxima de lote,
    retorna o número mínimo de lotes necessários para enviar todos os arquivos.
    Restrições:
    - Um lote pode conter no máximo 2 arquivos.
    - A soma dos tamanhos não pode exceder a capacidade máxima estipulada.
    """
    tamanhos.sort()

    menor =0 
    maior = len(tamanhos)-1
    lotes = 0

    while(menor <=maior):
        if (menor != maior) and ((tamanhos[menor] + tamanhos[maior]) <= capacidade):
            menor +=1

        maior -=1
        lotes +=1

    return lotes
def validar_codigo_barras(codigo: str) -> bool:
    """
    Valida um código de barras de acordo com 5 regras:
    1. Possuir exatamente 12 caracteres.
    2. Iniciar com um dígito numérico.
    3. Terminar com uma letra.
    4. Não possuir 3 caracteres idênticos em sequência.
    5. Não possuir 3 dígitos numéricos em sequência crescente.
    Retorna True se válido, False caso contrário.
    """
    if len(codigo) != 12:
        return False
    if not codigo[0].isdigit():
        return False
    if not codigo[-1].isalpha():
        return False

    for i in range(len(codigo) - 2):
        janela = codigo[i:i + 3]
        if janela[0] == janela[1] == janela[2]:
            return False
        if janela.isdigit():
            d0, d1, d2 = int(janela[0]), int(janela[1]), int(janela[2])
            if d1 == d0 + 1 and d2 == d1 + 1:
                return False

    return True

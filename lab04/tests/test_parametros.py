import math

import numpy as np
import pandas as pd
import pytest

from lab04.simulacao.parametros import FIM, INICIO, calcular, reescrever, sigma_comum, tabela


def _csv(tmp_path, grupos):
    linhas = [
        {"grupo": grupo, "horas_ate_merge": h}
        for grupo, horas in grupos.items()
        for h in horas
    ]
    caminho = tmp_path / "prs.csv"
    pd.DataFrame(linhas).to_csv(caminho, index=False)
    return caminho


def test_recupera_mu_e_sigma_de_uma_lognormal(tmp_path):
    rng = np.random.default_rng(42)
    csv = _csv(tmp_path, {
        "com_bot": rng.lognormal(math.log(20), 1.2, 5000),
        "sem_bot": rng.lognormal(math.log(8), 0.8, 5000),
    })
    p = calcular(csv)
    assert p["com_bot"].mediana_lognormal == pytest.approx(20, rel=0.05)
    assert p["com_bot"].sigma == pytest.approx(1.2, rel=0.05)
    assert p["sem_bot"].mediana_lognormal == pytest.approx(8, rel=0.05)
    assert p["sem_bot"].sigma == pytest.approx(0.8, rel=0.05)
    assert p["com_bot"].n == 5000


def test_recusa_hora_zero(tmp_path):
    with pytest.raises(ValueError):
        calcular(_csv(tmp_path, {"com_bot": [1.0, 0.0], "sem_bot": [2.0, 3.0]}))


def test_reescreve_so_o_bloco_marcado(tmp_path):
    rng = np.random.default_rng(1)
    csv = _csv(tmp_path, {"com_bot": rng.lognormal(2, 1, 30), "sem_bot": rng.lognormal(1, 1, 30)})
    cenario = tmp_path / "cenario.md"
    cenario.write_text(f"antes\n{INICIO}\npendente\n{FIM}\ndepois\n", encoding="utf-8")
    reescrever(cenario, tabela(calcular(csv)))
    texto = cenario.read_text(encoding="utf-8")
    assert texto.startswith("antes\n") and texto.endswith("depois\n")
    assert "pendente" not in texto and "| com_bot | 30 |" in texto
    assert "σ comum do cenário base:" in texto


def test_sigma_comum_e_a_media_dos_grupos(tmp_path):
    rng = np.random.default_rng(7)
    p = calcular(_csv(tmp_path, {"com_bot": rng.lognormal(0, 1, 50), "sem_bot": rng.lognormal(0, 2, 50)}))
    assert sigma_comum(p) == pytest.approx((p["com_bot"].sigma + p["sem_bot"].sigma) / 2)

"""Pruebas de las reglas de cierre (paso 9)."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.cierre import evaluar_cierre  # noqa: E402


def _df(filas):
    return pd.DataFrame(filas, columns=[
        "periodo", "energetico", "valor_op", "valor_cont", "estado", "justificacion"])


def test_todo_cuadrado_se_puede_cerrar():
    df = _df([
        ("2025-06", "diesel", 100, 100, "cuadrado", ""),
        ("2025-06", "gas_natural", 200, 198, "cuadrado", ""),
    ])
    res = evaluar_cierre(df)
    assert res.puede_cerrar
    assert res.bloqueos == []


def test_desviacion_sin_justificar_bloquea():
    df = _df([("2025-06", "electricidad_comprada", 105, 100, "desviacion", "")])
    res = evaluar_cierre(df)
    assert not res.puede_cerrar
    assert any("sin justificar" in b for b in res.bloqueos)


def test_desviacion_justificada_no_bloquea():
    df = _df([("2025-06", "electricidad_comprada", 105, 100, "desviacion", "parada 12/06")])
    res = evaluar_cierre(df)
    assert res.puede_cerrar
    assert res.bloqueos == []


def test_pendiente_por_falta_de_fuente_bloquea():
    df = _df([("2025-06", "diesel", 100, np.nan, "pendiente", "")])
    res = evaluar_cierre(df)
    assert not res.puede_cerrar
    assert any("falta fuente" in b for b in res.bloqueos)


def test_pendiente_por_valor_cero_solo_advierte():
    df = _df([("2025-06", "diesel", 0, 100, "pendiente", "")])
    res = evaluar_cierre(df)
    assert res.puede_cerrar          # advertencia no bloquea
    assert res.bloqueos == []
    assert any("mantención" in a for a in res.advertencias)


def test_mezcla_bloqueos_y_advertencias():
    df = _df([
        ("2025-06", "diesel", 100, 100, "cuadrado", ""),
        ("2025-06", "gas_natural", 110, 100, "desviacion", ""),   # bloqueo
        ("2025-06", "biomasa", 0, 50, "pendiente", ""),           # advertencia
        ("2025-06", "fuel_oil", 5, np.nan, "pendiente", ""),      # bloqueo
    ])
    res = evaluar_cierre(df)
    assert not res.puede_cerrar
    assert len(res.bloqueos) == 2
    assert len(res.advertencias) == 1

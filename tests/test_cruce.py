"""Pruebas del cruce operativo vs. contable (paso 3)."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import cruce  # noqa: E402
from engine.cruce import cruzar, CruceError  # noqa: E402


def _largo(filas):
    """Atajo: construye una tabla canónica larga desde tuplas
    (periodo, energetico, tipo, unidad, fuente, valor)."""
    return pd.DataFrame(filas, columns=[
        "periodo", "energetico", "tipo", "unidad", "fuente", "valor"])


@pytest.fixture
def op():
    return _largo([
        ("2025-01", "gas_natural", "combustible_fosil", "Nm3", "operativo", 1000),
        ("2025-01", "diesel", "combustible_fosil", "lt", "operativo", 300),
        ("2025-02", "gas_natural", "combustible_fosil", "Nm3", "operativo", 1100),
    ])


@pytest.fixture
def cont():
    return _largo([
        ("2025-01", "gas_natural", "combustible_fosil", "Nm3", "contable", 980),
        ("2025-01", "diesel", "combustible_fosil", "lt", "contable", 300),
        ("2025-02", "gas_natural", "combustible_fosil", "Nm3", "contable", 1150),
    ])


def test_columnas_y_orden(op, cont):
    res = cruzar(op, cont)
    assert list(res.columns) == cruce.COLUMNAS_CRUCE
    assert list(res["periodo"]) == sorted(res["periodo"])


def test_pivote_op_y_cont_en_una_fila(op, cont):
    res = cruzar(op, cont)
    fila = res[(res.periodo == "2025-01") & (res.energetico == "gas_natural")]
    assert len(fila) == 1
    assert fila.iloc[0]["valor_op"] == 1000
    assert fila.iloc[0]["valor_cont"] == 980
    assert fila.iloc[0]["unidad"] == "Nm3"


def test_una_fila_por_energetico_periodo(op, cont):
    res = cruzar(op, cont)
    # gas_natural en 2 periodos + diesel en 1 = 3 filas
    assert len(res) == 3


def test_lado_faltante_queda_nan(op):
    # Solo operativo: valor_cont debe ser NaN, valor_op presente.
    res = cruzar(op)
    assert res["valor_cont"].isna().all()
    assert not res["valor_op"].isna().any()


def test_energetico_solo_en_contable(op, cont):
    extra = _largo([
        ("2025-01", "biomasa", "combustible_biogenico", "ton", "contable", 50),
    ])
    res = cruzar(op, cont, extra)
    bio = res[res.energetico == "biomasa"].iloc[0]
    assert pd.isna(bio["valor_op"])
    assert bio["valor_cont"] == 50


def test_unidad_inconsistente_lanza_error(op):
    malo = _largo([
        ("2025-01", "gas_natural", "combustible_fosil", "lt", "contable", 1),
    ])
    with pytest.raises(CruceError, match="unidad"):
        cruzar(op, malo)


def test_tipo_inconsistente_lanza_error(op):
    malo = _largo([
        ("2025-01", "gas_natural", "combustible_biogenico", "Nm3", "contable", 1),
    ])
    with pytest.raises(CruceError, match="tipo"):
        cruzar(op, malo)


def test_fuente_desconocida_lanza_error():
    malo = _largo([
        ("2025-01", "diesel", "combustible_fosil", "lt", "sensor", 1),
    ])
    with pytest.raises(CruceError, match="[Ff]uente"):
        cruzar(malo)


def test_duplicado_misma_fuente_se_suma():
    # Dos archivos operativos del mismo energético/periodo → se suman.
    a = _largo([("2025-01", "diesel", "combustible_fosil", "lt", "operativo", 100)])
    b = _largo([("2025-01", "diesel", "combustible_fosil", "lt", "operativo", 50)])
    res = cruzar(a, b)
    assert res.iloc[0]["valor_op"] == 150


def test_sin_argumentos_lanza_error():
    with pytest.raises(CruceError):
        cruzar()

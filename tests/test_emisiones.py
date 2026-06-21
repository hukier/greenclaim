"""Pruebas de la capa derivada: energía (GJ) + emisiones (tCO₂eq) (paso 5)."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import emisiones  # noqa: E402
from engine.emisiones import (  # noqa: E402
    calcular_derivada,
    cargar_factores,
    Factor,
    Factores,
    FactoresError,
)


def _brecha(filas):
    """Atajo: tabla del paso 4 (solo las columnas que usa la capa derivada)."""
    return pd.DataFrame(filas, columns=["periodo", "energetico", "unidad", "valor_op"])


# Factores fijos para los tests (independientes del YAML del repo).
FAC = Factores(
    por_energetico={
        "gas_natural": Factor(factor_gj=0.04, factor_co2=0.05, biogenico=False),
        "biomasa": Factor(factor_gj=15.0, factor_co2=0.0, biogenico=True),
    },
    default=None,
)


def test_columnas_anadidas():
    res = calcular_derivada(_brecha([
        ("2025-01", "gas_natural", "Nm3", 1000),
    ]), FAC)
    for col in emisiones.COLUMNAS_DERIVADA:
        assert col in res.columns


def test_calculo_gj_y_co2():
    res = calcular_derivada(_brecha([
        ("2025-01", "gas_natural", "Nm3", 1000),
    ]), FAC)
    fila = res.iloc[0]
    assert fila["energia_gj"] == pytest.approx(40.0)      # 1000 * 0.04
    assert fila["emisiones_tco2eq"] == pytest.approx(2.0)  # 40 * 0.05
    assert fila["es_biogenico"] == False


def test_biomasa_emite_cero_fosil():
    res = calcular_derivada(_brecha([
        ("2025-01", "biomasa", "ton", 100),
    ]), FAC)
    fila = res.iloc[0]
    assert fila["energia_gj"] == pytest.approx(1500.0)   # 100 * 15
    assert fila["emisiones_tco2eq"] == 0.0
    assert fila["es_biogenico"] == True


def test_biogenico_cero_aunque_factor_co2_no_sea_cero():
    # Aunque el YAML traiga factor_co2 > 0, biogénico fuerza 0 emisiones fósiles.
    fac = Factores(por_energetico={
        "biomasa": Factor(factor_gj=10.0, factor_co2=0.9, biogenico=True),
    })
    res = calcular_derivada(_brecha([("2025-01", "biomasa", "ton", 5)]), fac)
    assert res.iloc[0]["emisiones_tco2eq"] == 0.0


def test_energetico_sin_factor_queda_nan_con_warning():
    res = None
    with pytest.warns(UserWarning, match="Sin factor"):
        res = calcular_derivada(_brecha([
            ("2025-01", "fuel_oil", "lt", 200),   # no está en FAC, default None
        ]), FAC)
    fila = res.iloc[0]
    assert pd.isna(fila["energia_gj"])
    assert pd.isna(fila["emisiones_tco2eq"])
    assert fila["es_biogenico"] == False


def test_valor_op_nan_propaga_nan():
    res = calcular_derivada(_brecha([
        ("2025-01", "gas_natural", "Nm3", np.nan),
    ]), FAC)
    assert pd.isna(res.iloc[0]["energia_gj"])
    assert pd.isna(res.iloc[0]["emisiones_tco2eq"])


def test_no_muta_entrada():
    df = _brecha([("2025-01", "gas_natural", "Nm3", 1000)])
    calcular_derivada(df, FAC)
    assert list(df.columns) == ["periodo", "energetico", "unidad", "valor_op"]


# --- carga y validación de factores ---

def test_cargar_factores_ok(tmp_path):
    ruta = tmp_path / "f.yaml"
    ruta.write_text(
        "energeticos:\n"
        "  diesel:\n    factor_gj: 0.0383\n    factor_co2: 0.074\n"
        "  biomasa:\n    factor_gj: 15\n    factor_co2: 0\n    biogenico: true\n"
        "default:\n  factor_gj: 0\n  factor_co2: 0\n",
        encoding="utf-8")
    fac = cargar_factores(str(ruta))
    assert fac.para("diesel").factor_gj == pytest.approx(0.0383)
    assert fac.para("biomasa").biogenico is True
    # Energético no listado cae al default (factor 0).
    assert fac.para("desconocido").factor_gj == 0.0


def test_factor_negativo_falla(tmp_path):
    ruta = tmp_path / "f.yaml"
    ruta.write_text(
        "energeticos:\n  diesel:\n    factor_gj: -1\n    factor_co2: 0.07\n",
        encoding="utf-8")
    with pytest.raises(FactoresError, match="negativo"):
        cargar_factores(str(ruta))


def test_campo_faltante_falla(tmp_path):
    ruta = tmp_path / "f.yaml"
    ruta.write_text(
        "energeticos:\n  diesel:\n    factor_gj: 0.04\n",   # falta factor_co2
        encoding="utf-8")
    with pytest.raises(FactoresError, match="factor_co2"):
        cargar_factores(str(ruta))

"""Pruebas de brecha + estado por umbral (paso 4)."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import brecha  # noqa: E402
from engine.brecha import calcular_brecha, cargar_umbrales, Umbrales, UmbralesError  # noqa: E402


def _cruce(filas):
    """Atajo: tabla de cruce desde tuplas
    (periodo, energetico, tipo, unidad, valor_op, valor_cont)."""
    return pd.DataFrame(filas, columns=[
        "periodo", "energetico", "tipo", "unidad", "valor_op", "valor_cont"])


# Umbrales fijos para los tests (no dependen del YAML del repo).
UMB = Umbrales(por_energetico={
    "electricidad_comprada": 2.0,
    "gas_natural": 4.0,
    "diesel": 5.0,
}, default=5.0)


def test_columnas_anadidas():
    res = calcular_brecha(_cruce([
        ("2025-01", "diesel", "combustible_fosil", "lt", 110, 100),
    ]), UMB)
    for col in brecha.COLUMNAS_BRECHA:
        assert col in res.columns


def test_brecha_abs_y_pct():
    res = calcular_brecha(_cruce([
        ("2025-01", "diesel", "combustible_fosil", "lt", 110, 100),
    ]), UMB)
    fila = res.iloc[0]
    assert fila["brecha_abs"] == 10
    assert fila["brecha_pct"] == pytest.approx(10.0)


def test_estado_cuadrado_dentro_de_umbral():
    # gas_natural umbral 4 %; brecha 3 % → cuadrado
    res = calcular_brecha(_cruce([
        ("2025-01", "gas_natural", "combustible_fosil", "Nm3", 103, 100),
    ]), UMB)
    assert res.iloc[0]["estado"] == "cuadrado"


def test_estado_frontera_es_cuadrado():
    # Exactamente en el umbral (≤): 4 % con umbral 4 % → cuadrado
    res = calcular_brecha(_cruce([
        ("2025-01", "gas_natural", "combustible_fosil", "Nm3", 104, 100),
    ]), UMB)
    assert res.iloc[0]["estado"] == "cuadrado"


def test_estado_desviacion_supera_umbral():
    # electricidad umbral 2 %; brecha 5 % → desviacion
    res = calcular_brecha(_cruce([
        ("2025-01", "electricidad_comprada", "electricidad_red", "kWh", 105, 100),
    ]), UMB)
    assert res.iloc[0]["estado"] == "desviacion"


def test_umbral_distinto_por_energetico():
    # Misma brecha 4.5 %: diesel (umbral 5) cuadrado; electricidad (umbral 2) desviacion
    res = calcular_brecha(_cruce([
        ("2025-01", "diesel", "combustible_fosil", "lt", 104.5, 100),
        ("2025-01", "electricidad_comprada", "electricidad_red", "kWh", 104.5, 100),
    ]), UMB)
    diesel = res[res.energetico == "diesel"].iloc[0]
    elec = res[res.energetico == "electricidad_comprada"].iloc[0]
    assert diesel["estado"] == "cuadrado"
    assert elec["estado"] == "desviacion"


def test_estado_pendiente_por_lado_faltante():
    res = calcular_brecha(_cruce([
        ("2025-01", "diesel", "combustible_fosil", "lt", 100, np.nan),
    ]), UMB)
    fila = res.iloc[0]
    assert fila["estado"] == "pendiente"
    assert pd.isna(fila["brecha_pct"])


def test_estado_pendiente_por_valor_cero():
    # Valor 0 por mantención → pendiente, aunque haya ambos lados.
    res = calcular_brecha(_cruce([
        ("2025-01", "diesel", "combustible_fosil", "lt", 0, 100),
    ]), UMB)
    assert res.iloc[0]["estado"] == "pendiente"


def test_division_por_cont_cero_no_rompe():
    res = calcular_brecha(_cruce([
        ("2025-01", "diesel", "combustible_fosil", "lt", 50, 0),
    ]), UMB)
    fila = res.iloc[0]
    assert pd.isna(fila["brecha_pct"])     # no inf
    assert fila["estado"] == "pendiente"   # cont 0 → pendiente
    assert fila["brecha_abs"] == 50


def test_no_muta_entrada():
    cruce = _cruce([("2025-01", "diesel", "combustible_fosil", "lt", 110, 100)])
    calcular_brecha(cruce, UMB)
    assert list(cruce.columns) == [
        "periodo", "energetico", "tipo", "unidad", "valor_op", "valor_cont"]


# --- carga y validación de umbrales ---

def test_cargar_umbrales_ok(tmp_path):
    ruta = tmp_path / "u.yaml"
    ruta.write_text("energeticos:\n  diesel: 5.0\ndefault: 3.0\n", encoding="utf-8")
    umb = cargar_umbrales(str(ruta))
    assert umb.para("diesel") == 5.0
    assert umb.para("desconocido") == 3.0   # cae al default


def test_umbral_negativo_falla(tmp_path):
    ruta = tmp_path / "u.yaml"
    ruta.write_text("energeticos:\n  diesel: -1\n", encoding="utf-8")
    with pytest.raises(UmbralesError, match="negativo"):
        cargar_umbrales(str(ruta))


def test_umbral_no_numerico_falla(tmp_path):
    ruta = tmp_path / "u.yaml"
    ruta.write_text("energeticos:\n  diesel: cinco\n", encoding="utf-8")
    with pytest.raises(UmbralesError, match="no numérico"):
        cargar_umbrales(str(ruta))


def test_sin_umbrales_falla(tmp_path):
    ruta = tmp_path / "u.yaml"
    ruta.write_text("energeticos: {}\n", encoding="utf-8")
    with pytest.raises(UmbralesError):
        cargar_umbrales(str(ruta))

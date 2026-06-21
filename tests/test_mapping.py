"""Pruebas del mapeo canónico + agregación mensual (paso 2)."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import mapping  # noqa: E402
from engine.mapping import (  # noqa: E402
    cargar_plantilla,
    aplicar_mapeo,
    PlantillaError,
)

# Plantilla mínima en YAML, reutilizable; se escribe a un archivo temporal.
YAML_BASE = """
empresa: prueba
lectura:
  header: 0
identidad:
  fecha: fecha
energeticos:
  - energetico: gas_natural
    tipo: fosil
    unidad: Nm3
    fuente: operativo
    columnas: [gn_a, gn_b]
    agregacion: sum
  - energetico: gas_natural
    tipo: fosil
    unidad: Nm3
    fuente: contable
    columnas: [gn_factura]
  - energetico: diesel
    tipo: fosil
    unidad: lt
    fuente: operativo
    columnas: [diesel_lt]
"""


@pytest.fixture
def plantilla(tmp_path):
    ruta = tmp_path / "map.yaml"
    ruta.write_text(YAML_BASE, encoding="utf-8")
    return cargar_plantilla(str(ruta))


@pytest.fixture
def df_crudo():
    # Dos meses; gas natural partido en gn_a + gn_b (operativo) y gn_factura
    # (contable); diesel solo operativo.
    return pd.DataFrame({
        "fecha": ["2025-01-05", "2025-01-20", "2025-02-10"],
        "gn_a": [100, 200, 50],
        "gn_b": [10, 20, 5],
        "gn_factura": [120, 210, 60],
        "diesel_lt": [30, 40, 25],
    })


def test_carga_plantilla_resuelve_enums(plantilla):
    assert plantilla.empresa == "prueba"
    assert plantilla.identidad.fecha == "fecha"
    assert len(plantilla.energeticos) == 3
    primero = plantilla.energeticos[0]
    assert primero.energetico.value == "gas_natural"
    assert primero.tipo.value == "combustible_fosil"   # alias 'fosil' resuelto
    assert primero.fuente.value == "operativo"
    assert primero.agregacion == "sum"                 # default aplicado


def test_suma_de_componentes(plantilla, df_crudo):
    canon = aplicar_mapeo(df_crudo, plantilla)
    # Gas natural operativo enero = (100+10) + (200+20) = 330
    fila = canon[(canon.periodo == "2025-01") &
                 (canon.energetico == "gas_natural") &
                 (canon.fuente == "operativo")]
    assert len(fila) == 1
    assert fila.iloc[0]["valor"] == 330


def test_agregacion_mensual(plantilla, df_crudo):
    canon = aplicar_mapeo(df_crudo, plantilla)
    # Dos filas de enero colapsan en una sola fila por periodo.
    enero_gn_op = canon[(canon.periodo == "2025-01") &
                        (canon.energetico == "gas_natural") &
                        (canon.fuente == "operativo")]
    assert len(enero_gn_op) == 1
    # Diesel operativo febrero = 25
    feb_diesel = canon[(canon.periodo == "2025-02") &
                       (canon.energetico == "diesel")]
    assert feb_diesel.iloc[0]["valor"] == 25


def test_separacion_operativo_contable(plantilla, df_crudo):
    canon = aplicar_mapeo(df_crudo, plantilla)
    gn_enero = canon[(canon.periodo == "2025-01") &
                     (canon.energetico == "gas_natural")]
    fuentes = set(gn_enero["fuente"])
    assert fuentes == {"operativo", "contable"}
    # Contable enero = 120 + 210 = 330 (independiente del operativo)
    cont = gn_enero[gn_enero.fuente == "contable"].iloc[0]["valor"]
    assert cont == 330


def test_energetico_en_una_sola_fuente(plantilla, df_crudo):
    canon = aplicar_mapeo(df_crudo, plantilla)
    diesel = canon[canon.energetico == "diesel"]
    assert set(diesel["fuente"]) == {"operativo"}   # nunca aparece contable


def test_columnas_canonicas_y_orden(plantilla, df_crudo):
    canon = aplicar_mapeo(df_crudo, plantilla)
    assert list(canon.columns) == mapping.COLUMNAS_CANONICAS
    # Ordenado por periodo, energetico, fuente
    assert list(canon["periodo"]) == sorted(canon["periodo"])


def test_agregacion_mean(tmp_path):
    yaml_mean = """
empresa: p
identidad:
  fecha: fecha
energeticos:
  - energetico: gas_natural
    tipo: fosil
    unidad: Nm3
    fuente: operativo
    columnas: [gn]
    agregacion: mean
"""
    ruta = tmp_path / "m.yaml"
    ruta.write_text(yaml_mean, encoding="utf-8")
    pl = cargar_plantilla(str(ruta))
    df = pd.DataFrame({"fecha": ["2025-01-01", "2025-01-31"], "gn": [100, 200]})
    canon = aplicar_mapeo(df, pl)
    assert canon.iloc[0]["valor"] == 150   # promedio, no suma


# --- validación de plantilla ---

def test_falta_clave_obligatoria(tmp_path):
    yaml_malo = """
identidad:
  fecha: fecha
energeticos:
  - energetico: gas_natural
    tipo: fosil
    unidad: Nm3
    fuente: operativo
    # falta 'columnas'
"""
    ruta = tmp_path / "x.yaml"
    ruta.write_text(yaml_malo, encoding="utf-8")
    with pytest.raises(PlantillaError, match="columnas"):
        cargar_plantilla(str(ruta))


def test_enum_invalido(tmp_path):
    yaml_malo = """
identidad:
  fecha: fecha
energeticos:
  - energetico: petroleo_crudo
    tipo: fosil
    unidad: lt
    fuente: operativo
    columnas: [x]
"""
    ruta = tmp_path / "x.yaml"
    ruta.write_text(yaml_malo, encoding="utf-8")
    with pytest.raises(PlantillaError, match="energetico"):
        cargar_plantilla(str(ruta))


def test_agregacion_invalida(tmp_path):
    yaml_malo = """
identidad:
  fecha: fecha
energeticos:
  - energetico: diesel
    tipo: fosil
    unidad: lt
    fuente: operativo
    columnas: [x]
    agregacion: max
"""
    ruta = tmp_path / "x.yaml"
    ruta.write_text(yaml_malo, encoding="utf-8")
    with pytest.raises(PlantillaError, match="agregacion"):
        cargar_plantilla(str(ruta))


def test_columna_declarada_ausente_en_df(plantilla):
    df = pd.DataFrame({"fecha": ["2025-01-01"], "gn_a": [1]})  # faltan otras
    with pytest.raises(PlantillaError, match="no están en el archivo"):
        aplicar_mapeo(df, plantilla)

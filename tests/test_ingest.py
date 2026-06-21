"""Pruebas de la ingesta y validación estructural (paso 1)."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import ingest  # noqa: E402

REQ = ["fecha", "equipo", "gas_natural_nm3"]
FECHAS = ["fecha"]
NUM = ["gas_natural_nm3"]


@pytest.fixture
def archivo_limpio(tmp_path):
    df = pd.DataFrame({
        "fecha": ["2025-06-01", "2025-06-02", "2025-06-03"],
        "equipo": ["caldera_1"] * 3,
        "gas_natural_nm3": [12010, 11980, 12100],
    })
    ruta = tmp_path / "limpio.csv"
    df.to_csv(ruta, index=False)
    return str(ruta)


def test_archivo_limpio_es_ok(archivo_limpio):
    res = ingest(archivo_limpio, required_columns=REQ,
                 date_columns=FECHAS, numeric_columns=NUM)
    assert res.ok
    assert res.errors == []
    assert res.rows == 3
    assert "gas_natural_nm3" in res.columns


def test_archivo_inexistente(tmp_path):
    res = ingest(str(tmp_path / "no_existe.csv"))
    assert not res.ok
    assert res.errors[0].code == "missing_file"


def test_formato_no_admitido(tmp_path):
    ruta = tmp_path / "datos.txt"
    ruta.write_text("hola")
    res = ingest(str(ruta))
    assert not res.ok
    assert res.errors[0].code == "bad_format"


def test_columna_obligatoria_faltante(tmp_path):
    df = pd.DataFrame({"fecha": ["2025-06-01"], "equipo": ["c1"]})
    ruta = tmp_path / "sin_gn.csv"
    df.to_csv(ruta, index=False)
    res = ingest(str(ruta), required_columns=REQ)
    assert not res.ok
    assert any(i.code == "missing_column" for i in res.errors)


def test_fecha_invalida(tmp_path):
    df = pd.DataFrame({
        "fecha": ["2025-06-01", "2025-13-40"],
        "equipo": ["c1", "c1"],
        "gas_natural_nm3": [10, 20],
    })
    ruta = tmp_path / "fecha_mala.csv"
    df.to_csv(ruta, index=False)
    res = ingest(str(ruta), required_columns=REQ,
                 date_columns=FECHAS, numeric_columns=NUM)
    assert not res.ok
    assert any(i.code == "bad_date" for i in res.errors)


def test_valor_no_numerico(tmp_path):
    df = pd.DataFrame({
        "fecha": ["2025-06-01", "2025-06-02"],
        "equipo": ["c1", "c1"],
        "gas_natural_nm3": [10, "s/d"],
    })
    ruta = tmp_path / "texto_en_numero.csv"
    df.to_csv(ruta, index=False)
    res = ingest(str(ruta), required_columns=REQ,
                 date_columns=FECHAS, numeric_columns=NUM)
    assert not res.ok
    assert any(i.code == "non_numeric" for i in res.errors)


def test_dato_faltante_es_solo_advertencia(tmp_path):
    df = pd.DataFrame({
        "fecha": ["2025-06-01", "2025-06-02"],
        "equipo": ["c1", "c1"],
        "gas_natural_nm3": [10, None],
    })
    ruta = tmp_path / "faltante.csv"
    df.to_csv(ruta, index=False)
    res = ingest(str(ruta), required_columns=REQ,
                 date_columns=FECHAS, numeric_columns=NUM)
    assert res.ok  # un faltante no bloquea
    assert any(i.code == "missing_values" for i in res.warnings)

"""Pruebas de la persistencia SQLite (paso 9)."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import persistencia as pe  # noqa: E402

PLANTA = "Planta Tipo"


def _df(filas):
    return pd.DataFrame(filas, columns=["periodo", "energetico", "justificacion"])


def _conn(tmp_path):
    return pe.conectar(str(tmp_path / "greenclaim.db"))


def test_guardar_y_cargar_justificaciones(tmp_path):
    conn = _conn(tmp_path)
    df = _df([
        ("2025-06", "gas_natural", "parada programada"),
        ("2025-06", "diesel", ""),   # vacía → no se guarda
    ])
    pe.guardar_justificaciones(conn, PLANTA, df, fecha="2026-06-14")
    guardadas = pe.cargar_justificaciones(conn, PLANTA)
    assert ("2025-06", "gas_natural") in guardadas
    assert guardadas[("2025-06", "gas_natural")]["nota"] == "parada programada"
    assert guardadas[("2025-06", "gas_natural")]["fecha"] == "2026-06-14"   # trazabilidad
    assert ("2025-06", "diesel") not in guardadas


def test_actualizar_justificacion_sobrescribe(tmp_path):
    conn = _conn(tmp_path)
    pe.guardar_justificaciones(conn, PLANTA, _df([("2025-06", "diesel", "v1")]), fecha="2026-06-01")
    pe.guardar_justificaciones(conn, PLANTA, _df([("2025-06", "diesel", "v2")]), fecha="2026-06-14")
    g = pe.cargar_justificaciones(conn, PLANTA)
    assert g[("2025-06", "diesel")]["nota"] == "v2"
    assert g[("2025-06", "diesel")]["fecha"] == "2026-06-14"


def test_nota_vacia_borra_existente(tmp_path):
    conn = _conn(tmp_path)
    pe.guardar_justificaciones(conn, PLANTA, _df([("2025-06", "diesel", "algo")]))
    pe.guardar_justificaciones(conn, PLANTA, _df([("2025-06", "diesel", "")]))
    assert ("2025-06", "diesel") not in pe.cargar_justificaciones(conn, PLANTA)


def test_aplicar_justificaciones_rellena_df(tmp_path):
    df = pd.DataFrame({
        "periodo": ["2025-06", "2025-06"],
        "energetico": ["diesel", "gas_natural"],
        "justificacion": ["", ""],
    })
    just = {("2025-06", "diesel"): {"nota": "mantención", "fecha": "2026-06-14"}}
    out = pe.aplicar_justificaciones(df, just)
    assert out.loc[out.energetico == "diesel", "justificacion"].iloc[0] == "mantención"
    assert out.loc[out.energetico == "gas_natural", "justificacion"].iloc[0] == ""
    assert list(df["justificacion"]) == ["", ""]   # no muta entrada


def test_cierre_registrar_y_estado(tmp_path):
    conn = _conn(tmp_path)
    assert pe.estado_cierre(conn, PLANTA, "2025-06") is None
    fecha = pe.registrar_cierre(conn, PLANTA, "2025-06", fecha="2026-06-14")
    assert fecha == "2026-06-14"
    assert pe.estado_cierre(conn, PLANTA, "2025-06") == "2026-06-14"


def test_anular_cierre_reabre(tmp_path):
    conn = _conn(tmp_path)
    pe.registrar_cierre(conn, PLANTA, "2025-06")
    pe.anular_cierre(conn, PLANTA, "2025-06")
    assert pe.estado_cierre(conn, PLANTA, "2025-06") is None


def test_persistencia_sobrevive_reconexion(tmp_path):
    ruta = str(tmp_path / "greenclaim.db")
    conn = pe.conectar(ruta)
    pe.guardar_justificaciones(conn, PLANTA, _df([("2025-06", "diesel", "nota")]))
    pe.registrar_cierre(conn, PLANTA, "2025-06", fecha="2026-06-14")
    conn.close()
    # Reabrir como en otra sesión.
    conn2 = pe.conectar(ruta)
    assert pe.cargar_justificaciones(conn2, PLANTA)[("2025-06", "diesel")]["nota"] == "nota"
    assert pe.estado_cierre(conn2, PLANTA, "2025-06") == "2026-06-14"

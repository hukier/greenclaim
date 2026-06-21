"""Persistencia en SQLite (paso 9 — headless).

Guarda las **justificaciones** por fila (con fecha, para trazabilidad) y el
**cierre** del período. Clave de una fila: ``(planta, periodo, energetico)``;
clave de un cierre: ``(planta, periodo)``.

No conoce la UI ni las reglas de cierre (eso es `engine.cierre`): solo lee y
escribe. Las funciones aceptan una conexión ``sqlite3`` ya abierta con
``conectar`` (que crea el esquema si falta).
"""
from __future__ import annotations

import sqlite3
from datetime import date

import pandas as pd

_ESQUEMA = (
    """CREATE TABLE IF NOT EXISTS justificaciones (
        planta TEXT, periodo TEXT, energetico TEXT, nota TEXT, fecha TEXT,
        PRIMARY KEY (planta, periodo, energetico)
    )""",
    """CREATE TABLE IF NOT EXISTS cierres (
        planta TEXT, periodo TEXT, fecha TEXT,
        PRIMARY KEY (planta, periodo)
    )""",
)


def conectar(path: str) -> sqlite3.Connection:
    """Abre (o crea) la base SQLite y garantiza el esquema."""
    conn = sqlite3.connect(path)
    for ddl in _ESQUEMA:
        conn.execute(ddl)
    conn.commit()
    return conn


def _vacia(nota) -> bool:
    return nota is None or pd.isna(nota) or str(nota).strip() == ""


def guardar_justificaciones(conn, planta, df, fecha=None) -> None:
    """Persiste la columna ``justificacion`` de ``df`` por fila. Nota vacía =
    borra la justificación guardada. La ``fecha`` (default hoy) queda registrada."""
    fecha = fecha or date.today().isoformat()
    for _, fila in df.iterrows():
        clave = (planta, fila["periodo"], fila["energetico"])
        nota = fila.get("justificacion")
        if _vacia(nota):
            conn.execute(
                "DELETE FROM justificaciones WHERE planta=? AND periodo=? AND energetico=?",
                clave,
            )
            continue
        conn.execute(
            """INSERT INTO justificaciones (planta, periodo, energetico, nota, fecha)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (planta, periodo, energetico)
               DO UPDATE SET nota=excluded.nota, fecha=excluded.fecha""",
            (*clave, str(nota).strip(), fecha),
        )
    conn.commit()


def cargar_justificaciones(conn, planta) -> dict:
    """Devuelve ``{(periodo, energetico): {'nota', 'fecha'}}`` de una planta."""
    cur = conn.execute(
        "SELECT periodo, energetico, nota, fecha FROM justificaciones WHERE planta=?",
        (planta,),
    )
    return {(p, e): {"nota": n, "fecha": f} for p, e, n, f in cur.fetchall()}


def aplicar_justificaciones(df: pd.DataFrame, justificaciones: dict) -> pd.DataFrame:
    """Rellena la columna ``justificacion`` de ``df`` desde el dict de
    ``cargar_justificaciones``. No muta la entrada."""
    df = df.copy()
    if "justificacion" not in df.columns:
        df["justificacion"] = ""

    def lookup(fila):
        guardada = justificaciones.get((fila["periodo"], fila["energetico"]))
        if guardada:
            return guardada["nota"]
        actual = fila["justificacion"]
        return "" if pd.isna(actual) else actual

    df["justificacion"] = df.apply(lookup, axis=1)
    return df


def registrar_cierre(conn, planta, periodo, fecha=None) -> str:
    """Marca el período como cerrado (con fecha). Devuelve la fecha usada."""
    fecha = fecha or date.today().isoformat()
    conn.execute(
        """INSERT INTO cierres (planta, periodo, fecha) VALUES (?, ?, ?)
           ON CONFLICT (planta, periodo) DO UPDATE SET fecha=excluded.fecha""",
        (planta, periodo, fecha),
    )
    conn.commit()
    return fecha


def anular_cierre(conn, planta, periodo) -> None:
    """Reabre un período cerrado."""
    conn.execute("DELETE FROM cierres WHERE planta=? AND periodo=?", (planta, periodo))
    conn.commit()


def estado_cierre(conn, planta, periodo):
    """Fecha de cierre del período, o ``None`` si está abierto."""
    cur = conn.execute(
        "SELECT fecha FROM cierres WHERE planta=? AND periodo=?", (planta, periodo)
    )
    fila = cur.fetchone()
    return fila[0] if fila else None

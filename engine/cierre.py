"""Reglas de cierre de una reconciliación (paso 9 — lógica de negocio headless).

El cierre del período se IMPIDE si:
  - hay un energético en ``desviacion`` sin justificación, o
  - hay un ``pendiente`` por falta de fuente obligatoria (operativo o contable).

Se ADVIERTE (sin bloquear) si:
  - hay un ``pendiente`` por valor 0 (típicamente mantención): dato no crítico.

No persiste nada ni conoce la UI: solo evalúa el DataFrame de reconciliación.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ResultadoCierre:
    """Veredicto de cierre: si se puede cerrar y por qué (no) se puede."""
    puede_cerrar: bool
    bloqueos: list = field(default_factory=list)
    advertencias: list = field(default_factory=list)


def _justificacion_vacia(df: pd.DataFrame) -> pd.Series:
    if "justificacion" not in df.columns:
        return pd.Series(True, index=df.index)
    just = df["justificacion"]
    return just.isna() | (just.astype(str).str.strip() == "")


def evaluar_cierre(df: pd.DataFrame) -> ResultadoCierre:
    """Evalúa si la reconciliación puede cerrarse. No muta la entrada."""
    bloqueos: list = []
    advertencias: list = []

    def etiqueta(fila):
        return f"{fila['energetico']} ({fila['periodo']})"

    vacia = _justificacion_vacia(df)
    desviadas = df[(df["estado"] == "desviacion") & vacia]
    for _, fila in desviadas.iterrows():
        bloqueos.append(f"{etiqueta(fila)}: desviación sin justificar.")

    pendientes = df[df["estado"] == "pendiente"]
    for _, fila in pendientes.iterrows():
        falta_fuente = pd.isna(fila["valor_op"]) or pd.isna(fila["valor_cont"])
        if falta_fuente:
            bloqueos.append(f"{etiqueta(fila)}: falta fuente obligatoria (operativo o contable).")
        else:
            advertencias.append(f"{etiqueta(fila)}: valor 0 (posible mantención), dato no crítico.")

    return ResultadoCierre(puede_cerrar=not bloqueos, bloqueos=bloqueos, advertencias=advertencias)

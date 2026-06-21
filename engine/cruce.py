"""Cruce operativo vs. contable (paso 3 del MVP).

Toma una o más tablas canónicas "largas" del paso 2 (``engine.mapping``) y las
combina en una tabla "ancha" con UNA fila por ``(energetico, periodo)``, con los
valores operativo y contable lado a lado:

    [periodo, energetico, tipo, unidad, valor_op, valor_cont]

Este módulo NO calcula brecha ni estado (eso es el paso 4): solo alinea ambos
lados. Donde falte un lado, su valor queda como ``NaN`` (el estado 'pendiente'
se decide después). La brecha se calculará en unidad nativa, por eso aquí se
valida que un mismo energético no mezcle unidades ni tipos entre fuentes.
"""
from __future__ import annotations

import pandas as pd

from engine.mapping import COLUMNAS_CANONICAS
from engine.schema import Fuente

# Columnas de la tabla de cruce (paso 3). La brecha/estado se añaden en el paso 4.
COLUMNAS_CRUCE = ["periodo", "energetico", "tipo", "unidad", "valor_op", "valor_cont"]

_FUENTE_A_COLUMNA = {
    Fuente.OPERATIVO.value: "valor_op",
    Fuente.CONTABLE.value: "valor_cont",
}


class CruceError(ValueError):
    """Inconsistencia que impide cruzar (p. ej. unidades distintas para un
    mismo energético entre operativo y contable)."""


def cruzar(*canonicos: pd.DataFrame) -> pd.DataFrame:
    """Combina tablas canónicas largas en la tabla de cruce ancha.

    Acepta N DataFrames (lo normal: uno del archivo operativo y otro del
    contable). Cada uno debe traer las columnas canónicas del paso 2
    ``[periodo, energetico, tipo, unidad, fuente, valor]``.

    Reglas:
      - pivota ``fuente`` a columnas ``valor_op`` / ``valor_cont``;
      - un lado ausente queda como ``NaN`` (no es error: será 'pendiente');
      - si un energético aparece con más de una ``unidad`` o ``tipo``,
        lanza ``CruceError`` (la brecha vive en unidad nativa).
    """
    if not canonicos:
        raise CruceError("cruzar() requiere al menos una tabla canónica.")

    largo = pd.concat(canonicos, ignore_index=True)

    faltantes = [c for c in COLUMNAS_CANONICAS if c not in largo.columns]
    if faltantes:
        raise CruceError(
            "Las tablas no tienen formato canónico; faltan columnas: "
            + ", ".join(repr(c) for c in faltantes)
        )

    if largo.empty:
        return pd.DataFrame(columns=COLUMNAS_CRUCE)

    fuentes_desconocidas = set(largo["fuente"]) - set(_FUENTE_A_COLUMNA)
    if fuentes_desconocidas:
        raise CruceError(
            "Fuente(s) no reconocida(s): "
            + ", ".join(repr(f) for f in sorted(fuentes_desconocidas))
            + f". Use: {', '.join(sorted(_FUENTE_A_COLUMNA))}."
        )

    # Consistencia: cada energético debe tener una sola unidad y un solo tipo.
    for campo in ("unidad", "tipo"):
        mezclas = largo.groupby("energetico")[campo].nunique()
        conflictivos = mezclas[mezclas > 1]
        if not conflictivos.empty:
            detalle = []
            for energetico in conflictivos.index:
                valores = sorted(largo.loc[largo["energetico"] == energetico, campo].unique())
                detalle.append(f"{energetico}: {', '.join(map(str, valores))}")
            raise CruceError(
                f"Un mismo energético mezcla '{campo}' entre fuentes — "
                + "; ".join(detalle)
            )

    # Pivote: una fila por (periodo, energetico, tipo, unidad); columnas por fuente.
    # tipo y unidad van en el índice (ya validados como únicos por energético).
    ancho = largo.pivot_table(
        index=["periodo", "energetico", "tipo", "unidad"],
        columns="fuente",
        values="valor",
        aggfunc="sum",
    ).reset_index()
    ancho.columns.name = None

    ancho = ancho.rename(columns=_FUENTE_A_COLUMNA)
    # Garantizar ambas columnas aunque una fuente no aparezca en ningún archivo.
    for col in ("valor_op", "valor_cont"):
        if col not in ancho.columns:
            ancho[col] = pd.NA

    ancho = ancho[COLUMNAS_CRUCE]
    ancho = ancho.sort_values(["periodo", "energetico"]).reset_index(drop=True)
    return ancho

"""Vocabulario canónico del MVP.

Por ahora solo fija los nombres genéricos que el motor usará en pasos
posteriores (mapeo y reconciliación). El núcleo del MVP son únicamente
energéticos; producción, materias primas, agua y químicos quedan fuera.
"""
from __future__ import annotations
from enum import Enum


class Energetico(str, Enum):
    GAS_NATURAL = "gas_natural"
    DIESEL = "diesel"
    FUEL_OIL = "fuel_oil"
    BIOMASA = "biomasa"
    ELECTRICIDAD = "electricidad_comprada"


class TipoEnergetico(str, Enum):
    FOSIL = "combustible_fosil"
    BIOGENICO = "combustible_biogenico"
    ELECTRICIDAD_RED = "electricidad_red"


class Fuente(str, Enum):
    OPERATIVO = "operativo"   # sensor / PI
    CONTABLE = "contable"     # factura / SAP


class Estado(str, Enum):
    CUADRADO = "cuadrado"
    DESVIACION = "desviacion"
    PENDIENTE = "pendiente"

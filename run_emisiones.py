"""Demo del paso 5: encadena mapeo (2) → cruce (3) → brecha (4) → derivada (5).
Muestra la tabla final completa con energía y emisiones.

    python make_sample_data.py && python make_sample_contable.py && python run_emisiones.py
"""
import os

import pandas as pd

from engine.mapping import cargar_plantilla, mapear_archivo
from engine.cruce import cruzar
from engine.brecha import cargar_umbrales, calcular_brecha
from engine.emisiones import cargar_factores, calcular_derivada

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CONFIG = os.path.join(HERE, "config")


def _mapear(plantilla_yaml: str, archivo: str):
    plantilla = cargar_plantilla(os.path.join(CONFIG, plantilla_yaml))
    resultado, canonico = mapear_archivo(os.path.join(DATA, archivo), plantilla)
    print(resultado.report())
    if canonico is None:
        raise SystemExit("  La ingesta falló; no se puede continuar.")
    return canonico


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)

    print("=" * 64)
    print("RECONCILIACIÓN COMPLETA · mapeo → cruce → brecha → emisiones")
    print("=" * 64)
    op = _mapear("mapping_ejemplo.yaml", "operativo_ejemplo.csv")
    cont = _mapear("mapping_ejemplo_contable.yaml", "contable_ejemplo.csv")

    cruzado = cruzar(op, cont)
    umbrales = cargar_umbrales(os.path.join(CONFIG, "umbrales.yaml"))
    recon = calcular_brecha(cruzado, umbrales)

    factores = cargar_factores(os.path.join(CONFIG, "factores.yaml"))
    final = calcular_derivada(recon, factores)

    print("\n  Tabla final (núcleo + capa derivada; factores PROVISIONALES):")
    print(final.to_string(index=False).replace("\n", "\n    "))

    fosil = final.loc[~final["es_biogenico"], "emisiones_tco2eq"].sum()
    print(f"\n  Total emisiones fósiles (tCO2eq): {fosil:.3f}")

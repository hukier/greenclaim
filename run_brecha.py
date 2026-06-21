"""Demo del paso 4: encadena mapeo (paso 2) → cruce (paso 3) → brecha + estado.

    python make_sample_data.py && python make_sample_contable.py && python run_brecha.py
"""
import os

from engine.mapping import cargar_plantilla, mapear_archivo
from engine.cruce import cruzar
from engine.brecha import cargar_umbrales, calcular_brecha

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
    print("=" * 64)
    print("BRECHA + ESTADO · operativo vs. contable (ejemplo)")
    print("=" * 64)
    op = _mapear("mapping_ejemplo.yaml", "operativo_ejemplo.csv")
    cont = _mapear("mapping_ejemplo_contable.yaml", "contable_ejemplo.csv")

    cruzado = cruzar(op, cont)
    umbrales = cargar_umbrales(os.path.join(CONFIG, "umbrales.yaml"))
    reconciliacion = calcular_brecha(cruzado, umbrales)

    print("\n  Tabla de reconciliación (brecha en unidad nativa + estado):")
    print(reconciliacion.to_string(index=False).replace("\n", "\n    "))

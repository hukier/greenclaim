"""Demo del paso 3: mapea un archivo operativo y uno contable (paso 2) y los
cruza en una tabla con valor_op vs valor_cont por energético y período.

    python make_sample_data.py && python make_sample_contable.py && python run_cruce.py
"""
import os

from engine.mapping import cargar_plantilla, mapear_archivo
from engine.cruce import cruzar

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CONFIG = os.path.join(HERE, "config")


def _mapear(plantilla_yaml: str, archivo: str):
    plantilla = cargar_plantilla(os.path.join(CONFIG, plantilla_yaml))
    resultado, canonico = mapear_archivo(os.path.join(DATA, archivo), plantilla)
    print(resultado.report())
    if canonico is None:
        raise SystemExit("  La ingesta falló; no se puede cruzar.")
    return canonico


if __name__ == "__main__":
    print("=" * 64)
    print("CRUCE · operativo vs. contable (ejemplo)")
    print("=" * 64)
    op = _mapear("mapping_ejemplo.yaml", "operativo_ejemplo.csv")
    cont = _mapear("mapping_ejemplo_contable.yaml", "contable_ejemplo.csv")

    cruzado = cruzar(op, cont)
    print("\n  Tabla de cruce (sin brecha aún — eso es el paso 4):")
    print(cruzado.to_string(index=False).replace("\n", "\n    "))

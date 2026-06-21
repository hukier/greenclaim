"""Demo del paso 2: carga una plantilla, lee+valida el archivo con la ingesta
y muestra la tabla canónica mensual. Ejecutar:

    python make_sample_data.py && python make_sample_arauco.py && python run_mapping.py
"""
import os

from engine.mapping import cargar_plantilla, mapear_archivo

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CONFIG = os.path.join(HERE, "config")


def correr(nombre_plantilla: str, archivo: str) -> None:
    plantilla = cargar_plantilla(os.path.join(CONFIG, nombre_plantilla))
    resultado, canonico = mapear_archivo(os.path.join(DATA, archivo), plantilla)
    print(resultado.report())
    if canonico is None:
        print("  (no se mapeó: la ingesta falló)\n")
        return
    print("  Tabla canónica (periodo × energético × fuente):")
    print(canonico.to_string(index=False).replace("\n", "\n    "))
    print()


if __name__ == "__main__":
    print("=" * 64)
    print("MAPEO · ejemplo genérico (CSV simple)")
    print("=" * 64)
    correr("mapping_ejemplo.yaml", "operativo_ejemplo.csv")

    print("=" * 64)
    print("MAPEO · CELULOSA_Arauco_tipo (header=4, fila de unidades, gas partido)")
    print("=" * 64)
    correr("mapping_celulosa_arauco.yaml", "CELULOSA_Arauco_tipo.xlsx")

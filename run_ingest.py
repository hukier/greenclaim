"""Demo del paso 1: corre la ingesta sobre los archivos de ejemplo y muestra
el reporte de validación. Ejecutar:  python run_ingest.py
"""
import os

from engine import ingest

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# Estas listas las proveerá la plantilla de mapeo de cada empresa (paso 2).
# Aquí van fijas solo para la demo.
REQUERIDAS = ["fecha", "equipo", "gas_natural_nm3", "diesel_lt", "electricidad_kwh"]
FECHAS = ["fecha"]
NUMERICAS = ["gas_natural_nm3", "diesel_lt", "electricidad_kwh"]


def correr(nombre: str) -> None:
    ruta = os.path.join(DATA, nombre)
    res = ingest(ruta, required_columns=REQUERIDAS,
                 date_columns=FECHAS, numeric_columns=NUMERICAS)
    print(res.report())
    if res.ok and res.preview is not None:
        print("  Vista previa:")
        print(res.preview.to_string(index=False).replace("\n", "\n    "))
    print()


if __name__ == "__main__":
    print("=" * 64)
    print("INGESTA · archivo limpio")
    print("=" * 64)
    correr("operativo_ejemplo.csv")

    print("=" * 64)
    print("INGESTA · archivo con problemas")
    print("=" * 64)
    correr("operativo_roto.csv")

"""Demo del paso 6 (entregable final): mapeo → cruce → brecha → emisiones →
export. Genera data/borrador_ejemplo.xlsx y muestra en consola qué se exportó.

    python make_sample_data.py && python make_sample_contable.py && python run_export.py
"""
import os
from datetime import date

from engine.mapping import cargar_plantilla, mapear_archivo
from engine.cruce import cruzar
from engine.brecha import cargar_umbrales, calcular_brecha
from engine.emisiones import cargar_factores, calcular_derivada
from engine.export import exportar_excel

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CONFIG = os.path.join(HERE, "config")


def _mapear(plantilla_yaml: str, archivo: str):
    plantilla = cargar_plantilla(os.path.join(CONFIG, plantilla_yaml))
    resultado, canonico = mapear_archivo(os.path.join(DATA, archivo), plantilla)
    if canonico is None:
        print(resultado.report())
        raise SystemExit("  La ingesta falló; no se puede exportar.")
    return canonico


if __name__ == "__main__":
    op = _mapear("mapping_ejemplo.yaml", "operativo_ejemplo.csv")
    cont = _mapear("mapping_ejemplo_contable.yaml", "contable_ejemplo.csv")

    cruzado = cruzar(op, cont)
    recon = calcular_brecha(cruzado, cargar_umbrales(os.path.join(CONFIG, "umbrales.yaml")))
    final = calcular_derivada(recon, cargar_factores(os.path.join(CONFIG, "factores.yaml")))

    meta = {
        "planta": "Planta Tipo (demo)",
        "periodo": "2025-06",
        "generado_en": date.today().isoformat(),
    }
    salida = os.path.join(DATA, "borrador_ejemplo.xlsx")
    datos = exportar_excel(final, meta, salida)

    print("=" * 64)
    print("EXPORT · borrador de reconciliación")
    print("=" * 64)
    print(f"  Archivo:  {datos['path']}")
    print(f"  Filas:    {datos['n_filas']}")
    print(f"  Estados:  {datos['por_estado']}")
    print(f"  Energía total (GJ):        {datos['energia_gj_total']:.3f}")
    print(f"  Emisiones fósiles (tCO2eq): {datos['emisiones_tco2eq_total']:.3f}")
    n = datos["desviaciones_sin_justificar"]
    if n:
        print(f"  ⚠ {n} desviación(es) sin justificar — requieren nota para cerrar.")
    else:
        print("  Sin desviaciones sin justificar.")

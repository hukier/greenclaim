"""Genera un archivo CONTABLE de ejemplo (factura/SAP mensual) que parea con
`operativo_ejemplo.csv` para demostrar el cruce (paso 3). Los valores difieren
un poco de los del operativo: esa diferencia será la brecha del paso 4.
"""
import os
import pandas as pd

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "data")
os.makedirs(OUT, exist_ok=True)

# Factura del mes 2025-06 (una fila mensual). Totales algo distintos a los
# del operativo (op: gas 96195, diesel 2448, electricidad 394790). La
# electricidad se aleja ~3.9 % para que el demo muestre una 'desviacion'
# (umbral electricidad ±2 %); gas y diesel quedan 'cuadrado'.
contable = pd.DataFrame({
    "fecha_factura": ["2025-06-30"],
    "gas_natural_nm3": [95000],
    "diesel_lt": [2500],
    "electricidad_kwh": [380000],
})
contable.to_csv(os.path.join(OUT, "contable_ejemplo.csv"), index=False)

print("Generado:")
print("  data/contable_ejemplo.csv")

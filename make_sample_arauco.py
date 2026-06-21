"""Genera un archivo de ejemplo que IMITA la estructura del export real tipo
'CELULOSA_Arauco_tipo' para probar el mapeo (paso 2) sin depender del dataset
real. Características replicadas:
  - 4 filas de metadatos arriba; encabezado en la fila índice 4 (header=4)
  - una fila de UNIDADES justo bajo el encabezado (se descarta con skiprows)
  - gas natural partido en dos columnas de PI (se SUMAN)
  - días de mantención con valor 0
  - varios meses para probar la agregación mensual
"""
import os
import pandas as pd

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "data")
os.makedirs(OUT, exist_ok=True)

filas = [
    ["Celulosa Arauco — Reporte operativo mensual", "", "", "", "", ""],
    ["Planta: tipo", "", "", "", "", ""],
    ["Uso interno / confidencial", "", "", "", "", ""],
    ["", "", "", "", "", ""],
    # índice 4: ENCABEZADO
    ["Fecha", "GN Caldera 1", "GN Caldera 2", "Petroleo Diesel", "Biomasa", "Energia Comprada"],
    # índice 5: UNIDADES (a descartar con skiprows)
    ["", "Nm3", "Nm3", "lt", "ton", "kWh"],
    # datos (desde índice 6)
    ["2025-01-05", 120000, 80000, 4200, 950, 510000],
    ["2025-01-15", 118500, 0,      0,    980, 505000],   # mantención caldera 2 + diesel
    ["2025-01-25", 121000, 79500,  4100, 0,   498000],
    ["2025-02-05", 119000, 81000,  4300, 1010, 512000],
    ["2025-02-15", 0,      0,      0,    0,    0],         # mantención total
    ["2025-02-25", 122500, 80500,  4250, 990, 507000],
]

bruto = pd.DataFrame(filas)
ruta = os.path.join(OUT, "CELULOSA_Arauco_tipo.xlsx")
bruto.to_excel(ruta, index=False, header=False)

print("Generado:")
print("  data/CELULOSA_Arauco_tipo.xlsx")

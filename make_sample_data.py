"""Genera archivos de ejemplo para probar la ingesta sin depender del
dataset real. Crea un export 'operativo' limpio y uno 'roto' que dispara
varias validaciones."""
import os
import pandas as pd

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "data")
os.makedirs(OUT, exist_ok=True)

fechas = pd.date_range("2025-06-01", periods=10, freq="D").strftime("%Y-%m-%d")

operativo = pd.DataFrame({
    "fecha": fechas,
    "equipo": ["caldera_1"] * 10,
    "gas_natural_nm3": [12010, 11980, 12100, 0, 0, 12050, 11990, 12030, 12075, 11960],
    "diesel_lt": [340, 355, 0, 0, 0, 350, 348, 360, 351, 344],
    "electricidad_kwh": [48200, 47900, 48100, 5200, 5100, 48050, 47980, 48230, 48110, 47920],
})
operativo.to_csv(os.path.join(OUT, "operativo_ejemplo.csv"), index=False)

# Archivo con problemas: falta 'electricidad_kwh', una fecha inválida,
# y texto en una columna numérica.
roto = operativo.drop(columns=["electricidad_kwh"]).copy()
roto["diesel_lt"] = roto["diesel_lt"].astype(object)   # permitir texto en la demo
roto.loc[2, "fecha"] = "2025-13-40"        # fecha imposible
roto.loc[4, "diesel_lt"] = "s/d"           # texto en columna numérica
roto.to_csv(os.path.join(OUT, "operativo_roto.csv"), index=False)

print("Generados:")
for f in ("operativo_ejemplo.csv", "operativo_roto.csv"):
    print("  data/" + f)

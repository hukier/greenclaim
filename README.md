# GreenClaim — Motor MVP

Motor de reconciliación de energía y emisiones (headless, independiente de la UI).
Construido por pasos; este repo va por el **paso 1: ingesta + validación estructural**.

## Estructura
```
engine/        motor (sin UI)
  ingest.py      lectura CSV/XLSX + validación estructural
  schema.py      vocabulario canónico (energéticos, estados)
config/        plantillas de mapeo por empresa (paso 2)
data/          archivos de entrada (no versionados)
tests/         pruebas pytest
```

## Entorno
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Demo
```bash
python make_sample_data.py   # genera archivos de ejemplo en data/
python run_ingest.py         # corre la ingesta y muestra el reporte
```

## Pruebas
```bash
pytest -q
```

## Alcance del paso 1
La ingesta valida: existencia del archivo, formato admitido (CSV/XLSX),
archivo no vacío, columnas obligatorias, fechas parseables y columnas
numéricas sin texto. Un dato faltante en una columna numérica es solo
advertencia, no bloquea. El mapeo al modelo canónico y la reconciliación
llegan en pasos posteriores.

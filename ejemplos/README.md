# Archivos de prueba para la carga

Pareja lista para probar el panel **"Subir archivos"** de la app (también en la
versión online de Streamlit) **sin errores de columnas**.

## Cómo usarlos

1. Descargá los dos CSV de esta carpeta:
   - `operativo_prueba.csv` (lecturas de sensores / PI)
   - `contable_prueba.csv` (factura / SAP)
2. En la app, en la barra lateral, elegí **"Subir archivos"**.
3. Subí cada archivo y elegí su plantilla:

   | Archivo a subir | Campo | Plantilla a elegir |
   |---|---|---|
   | `operativo_prueba.csv` | Archivo operativo (PI) | `mapping_prueba.yaml` |
   | `contable_prueba.csv` | Archivo contable (SAP) | `mapping_prueba_contable.yaml` |

4. Poné un nombre de planta y listo: se reconcilia el período **2025-05**.

## Qué deberías ver

Cinco energéticos con estados variados (para mostrar todos los casos):

| Energético | Estado | Por qué |
|---|---|---|
| gas_natural | cuadrado | brecha +0.8 % (≤ umbral) |
| electricidad_comprada | cuadrado | brecha +0.4 % |
| biomasa | cuadrado | brecha +1.4 % (biogénico → emisiones 0) |
| diesel | desviación | brecha +9.6 % (> umbral 5 %) → pide justificación |
| fuel_oil | pendiente | falta el lado contable (no está en la factura) |

> Los factores y umbrales son **provisionales** (configurables en `config/`),
> no valores oficiales.

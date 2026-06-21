# GreenClaim — Motor MVP

Motor de reconciliación de energía y emisiones (B2B, manufactura). Concilia el
dato operativo (sensor / PI) contra el contable (factura / SAP), detecta brechas
y produce un borrador para revisión ambiental. Etapa: construcción del MVP.

## Cómo trabajar en este repo (reglas)
- Avanza por pasos. No saltes al siguiente sin terminar y validar el actual.
- El motor es **headless** e independiente de la UI. La UI (Streamlit) viene después.
- No inventes factores de conversión/emisión ni umbrales "oficiales": son
  **provisionales y configurables**, a validar con especialistas. No los cablees como verdad.
- Núcleo = **solo energéticos**. Producción, materias primas, agua y químicos
  quedan fuera (no generan fila de reconciliación).
- Idioma del proyecto: **español** (código, comentarios, mensajes, tests).
- Antes de un cambio grande de diseño, explica y propone; no rehagas la arquitectura por tu cuenta.

## Stack
- Núcleo: Python 3.11+ con pandas (lectura, agregación, cruce, brecha).
- UI (después): Streamlit.
- Persistencia: SQLite. Config: YAML (plantilla de mapeo + umbrales + factores).
- Export (después): Excel (openpyxl/xlsxwriter) + PDF.

## Modelo de datos canónico
Una fila de reconciliación = **un energético × período**. Campos:
- `energetico` · `tipo` (fosil | biogenico | electricidad_red)
- `valor_op` (PI) · `valor_cont` (SAP) · `unidad` (nativa: Nm³ / lt / ton / kWh)
- `brecha_abs` = valor_op − valor_cont · `brecha_pct` = brecha_abs / valor_cont × 100
- `energia_gj` (derivado, factor pendiente) · `emisiones_tco2eq` (derivado, factor pendiente; biogénico = 0 fósil)
- `estado` (cuadrado | desviacion | pendiente) · `justificacion` (nota + fecha)

La brecha se calcula en **unidad nativa**. GJ y emisiones son una capa derivada
posterior que NO bloquea el núcleo.

Energéticos del núcleo: `gas_natural`, `diesel`, `fuel_oil` (fósiles),
`biomasa` (biogénico, factor fósil 0), `electricidad_comprada` (red).

## Flujo de datos (motor: 5 etapas + export)
1. Ingesta + validación estructural — **HECHO**
2. Mapeo canónico + agregación — **HECHO**
3. Cruce operativo vs. contable — **HECHO**
4. Brecha + estado (umbral por energético) — **HECHO**
5. Energía + emisiones (capa derivada) — **HECHO**
6. Export del borrador (Excel) — **HECHO** · motor headless COMPLETO

Entrada: **dos archivos separados** (operativo y contable). Salida: tabla de
reconciliación + resumen + borrador exportable.

## Reglas de negocio
- Estados: `cuadrado` (brecha ≤ umbral), `desviacion` (> umbral; requiere
  justificación para cerrar), `pendiente` (falta lado op o cont, o valor 0 por mantención).
- Umbral **por energético** (provisional, en YAML): electricidad ±2 %,
  gas_natural ±4 %, diesel ±5 %, fuel_oil ±5 %, biomasa ±7 %.
- Cierre: impide si falta fuente obligatoria o hay desviación sin justificar;
  advierte si falta un dato no crítico.
- Trazabilidad: cada valor recuerda su archivo origen; la justificación lleva fecha.

## Estado del proyecto
- **Paso 1 HECHO y testeado**: `engine/ingest.py`, `tests/test_ingest.py`
  (7 pruebas verdes), `run_ingest.py`, `make_sample_data.py`.
- **Paso 2 HECHO y testeado**: `engine/mapping.py` (`cargar_plantilla`,
  `aplicar_mapeo`, `mapear_archivo`; `Plantilla`/`PlantillaError`),
  `config/mapping_ejemplo.yaml`, `config/mapping_celulosa_arauco.yaml`
  (header=4 + fila de unidades vía `skiprows` + gas partido que se suma),
  `tests/test_mapping.py` (11 pruebas verdes), `run_mapping.py`,
  `make_sample_arauco.py`. `engine.ingest` aceptó `skiprows`. Salida canónica
  larga `[periodo, energetico, tipo, unidad, fuente, valor]`. 18 pruebas en total.
- **Paso 3 HECHO y testeado**: `engine/cruce.py` (`cruzar(*canonicos)`,
  `CruceError`), `tests/test_cruce.py` (10 pruebas verdes), `run_cruce.py`,
  `make_sample_contable.py`, `config/mapping_ejemplo_contable.yaml`. Pivota
  `fuente`→`valor_op`/`valor_cont`; una fila por `(energetico, periodo)`; lado
  ausente = `NaN`; valida unidad/tipo consistentes por energético. Salida
  `[periodo, energetico, tipo, unidad, valor_op, valor_cont]`. 28 pruebas en
  total. Pendiente menor: trazabilidad por archivo de origen (diferida para no
  romper el contrato de 6 columnas del paso 2).
- **Paso 4 HECHO y testeado**: `engine/brecha.py` (`cargar_umbrales`,
  `calcular_brecha`; `Umbrales`/`UmbralesError`), `config/umbrales.yaml`
  (umbrales provisionales por energético + `default`), `tests/test_brecha.py`
  (14 pruebas verdes), `run_brecha.py`. Añade `[brecha_abs, brecha_pct, estado]`
  al cruce; brecha en unidad nativa; estado `pendiente` por lado faltante o
  valor 0, `cuadrado`/`desviacion` según `|brecha_pct|` vs umbral. 42 pruebas
  en total.
- **Paso 5 HECHO y testeado**: `engine/emisiones.py` (`cargar_factores`,
  `calcular_derivada`; `Factor`/`Factores`/`FactoresError`),
  `config/factores.yaml` (factores PROVISIONALES por energético + `default`;
  `biogenico: true` en biomasa), `tests/test_emisiones.py` (10 pruebas verdes),
  `run_emisiones.py`. Capa OPCIONAL: añade `[energia_gj, emisiones_tco2eq,
  es_biogenico]` desde el lado operativo; biogénico ⇒ emisiones fósiles 0; sin
  factor ⇒ NaN + warning (no rompe). `factor_co2` en tCO₂eq/GJ. 52 pruebas en total.
- **Paso 6 HECHO y testeado**: `engine/export.py` (`exportar_excel(df_final,
  meta, path)`, `COLUMNAS_REPORTE`), `tests/test_export.py` (8 pruebas verdes),
  `run_export.py`. `.xlsx` con hojas `Reconciliacion` (orden fijo de columnas +
  color de fondo por estado: verde/rojo/amarillo) y `Resumen` (totales por
  energético, conteo por estado, metadata, advertencia visible si hay
  desviación sin justificar). `meta` requiere `planta/periodo/generado_en`.
  Devuelve dict-resumen. PDF: anotado deseable post-MVP, NO implementado.
  **60 pruebas en total.**
- `engine/schema.py`: enums canónicos (`Energetico`, `TipoEnergetico`, `Fuente`, `Estado`).
- **Paso 7 HECHO**: UI Streamlit. `ui/app.py` (tabla con color por estado vía
  Pandas Styler + `column_config`, filtros por energético/estado, badges de
  conteo, aviso de desviación sin justificar, descarga del borrador Excel),
  `ui/pipeline.py` (puente UI↔motor: `construir_reconciliacion`,
  `reconciliacion_demo`), `.streamlit/config.toml` (tema verde),
  `requirements-ui.txt`. Verificado con `AppTest` (sin excepciones, filtros OK).
  Skill instalado: `developing-with-streamlit` (oficial). Streamlit 1.58.
- **Paso 8 HECHO**: panel de fuentes en el sidebar (`panel_fuentes` en
  `ui/app.py`): radio demo vs subir archivos; `st.file_uploader` para operativo
  y contable + `selectbox` de plantilla por archivo + nombre de planta. Helpers
  en `ui/pipeline.py`: `plantillas_disponibles`, `guardar_subida` (vuelca a
  temporal, `engine.ingest` lee por ruta), `etiqueta_periodo`. Muestra avisos de
  validación (expander con `report()`) y errores claros (`PipelineError`).
  `construir_reconciliacion` ahora devuelve `(final, avisos)`. Verificado
  headless (carga, error con archivo roto) y con `AppTest` (ambos modos).
  Diseño visual: se pulirá al final (pasos 8–10 priorizan lógica).
- **Paso 9 HECHO**: justificación + cierre + SQLite. `engine/cierre.py`
  (`evaluar_cierre` → `ResultadoCierre` con bloqueos/advertencias: desviación sin
  justificar y pendiente por falta de fuente BLOQUEAN; pendiente por valor 0
  ADVIERTE), `engine/persistencia.py` (SQLite: justificaciones con fecha + cierres,
  `conectar/guardar_justificaciones/cargar_justificaciones/aplicar_justificaciones/
  registrar_cierre/anular_cierre/estado_cierre`). UI: `seccion_justificaciones`
  (`st.data_editor` editable solo en justificación, guarda en DB) y
  `seccion_cierre` (cerrar/reabrir). `tests/test_cierre.py` (6) +
  `tests/test_persistencia.py` (7). DB en `data/greenclaim.db` (gitignored).
  Verificado headless y `AppTest` (justificar → habilita cierre → cerrar → persiste).
  **73 pruebas en total.**
- **Paso 10 HECHO**: resumen + pulido visual. `seccion_resumen` (KPIs con
  `st.metric(border=True)` en `st.container(horizontal=True)`: energía total,
  emisiones fósiles, conteo cuadrado/desviacion/pendiente). Detalle,
  justificaciones y cierre en cards (`st.container(border=True)`) con subheaders
  e iconos Material. Tema verde de marca en `.streamlit/config.toml` (fuente
  Inter, paleta semántica alineada a los estados, radios/bordes) — **solo config
  nativa, sin CSS**. Verificado con `AppTest` (KPIs OK) y arranque real (tema
  parsea sin errores). **UI Streamlit COMPLETA (pasos 7–10). MVP terminado.**
- **Rediseño "Cuadratura mensual" HECHO** (sobre `ui/app.py`, a partir de un
  mockup del cliente): barra superior verde oscuro con logo + badge CORPORATIVO +
  avatar (`barra_superior`), título de dos tonos, **3 KPI cards reales** (Líneas
  cuadradas, Desviación promedio, Energía total — sin métricas inventadas),
  "tabla" de fuentes por fila con `st.columns` + pills `st.badge` + `st.segmented_control`
  para filtrar, y **acción de auditoría por fila**: "Justificar dato" abre
  `st.dialog` que persiste en SQLite; "✓ Revisado" si cuadrada/justificada. Usa
  **CSS/HTML propio** (`inyectar_estilos`) — excepción al "no CSS" del tema, por
  pedido explícito. Verificado con `AppTest` (sin excepciones, KPIs/botón/aviso)
  y arranque real (health 200, sin errores). 73 pruebas siguen verdes.

## Pendientes anotados
- **Trazabilidad por archivo de origen** (columnas `archivo_op` / `archivo_cont`):
  diferida. Retomar en un paso futuro propagando el origen desde `mapear_archivo`
  hasta el cruce, **sin romper el contrato de columnas** del cruce
  (`[periodo, energetico, tipo, unidad, valor_op, valor_cont]`) ni el del paso 2.

## Estructura
`engine/` motor headless · `config/` plantillas YAML · `data/` entradas (no versionado) · `tests/` pytest · `ui/` Streamlit (consume el motor).

## Comandos
- Setup: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt`
- Demo: `python make_sample_data.py && python run_ingest.py`
- Tests: `pytest -q`
- UI: `pip install -r requirements-ui.txt && streamlit run ui/app.py`

---

## Siguiente etapa: UI Streamlit (pasos 7–10)
El motor headless está COMPLETO. La UI consume el motor; no reescribe lógica de
negocio. Construir por pasos, validando cada uno (igual que el motor).

- **Paso 7** — Tabla de reconciliación — **HECHO** (ver Estado del proyecto).
- **Paso 8** — Panel de fuentes + carga — **HECHO** (ver Estado del proyecto).
- **Paso 9** — Justificación + cierre + SQLite — **HECHO** (ver Estado del proyecto).
- **Paso 10** — Resumen + pulido — **HECHO** (ver Estado del proyecto).

**MVP COMPLETO** (motor 1–6 + UI 7–10). Ideas post-MVP: export a PDF; trazabilidad
por archivo de origen (ver Pendientes); más plantas/plantillas reales; multipágina;
afinar tema/UX con feedback del cliente.

Anotado deseable post-MVP: export a PDF (una página con la misma info).
Mantener headless el motor; UI en español. Respetar modelo canónico y reglas.

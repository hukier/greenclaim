"""Puente UI ↔ motor headless (paso 7+).

Encadena las cinco etapas del motor + el modelo de export para entregar a la UI
una única tabla de reconciliación final. NO contiene lógica de negocio: solo
orquesta llamadas al paquete ``engine``. Reutilizable por la carga de archivos
(paso 8).
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys
import tempfile
from datetime import date

# La UI se ejecuta con `streamlit run ui/app.py`; Streamlit pone ui/ en el path,
# no la raíz del repo. La agregamos para poder importar `engine`.
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from engine.mapping import cargar_plantilla, mapear_archivo  # noqa: E402
from engine.cruce import cruzar  # noqa: E402
from engine.brecha import cargar_umbrales, calcular_brecha  # noqa: E402
from engine.emisiones import cargar_factores, calcular_derivada  # noqa: E402

DATA = os.path.join(RAIZ, "data")
CONFIG = os.path.join(RAIZ, "config")


class PipelineError(RuntimeError):
    """Una etapa del motor rechazó la entrada (ingesta inválida, etc.)."""


def construir_reconciliacion(op_path, op_yaml, cont_path, cont_yaml,
                             umbrales_yaml, factores_yaml):
    """Corre el flujo completo (mapeo → cruce → brecha → emisiones).

    Devuelve ``(df_final, avisos)`` donde ``avisos`` es la lista de
    ``IngestResult`` (operativo, contable) para que la UI muestre las
    validaciones. Lanza ``PipelineError`` si la ingesta de algún archivo falla,
    con el reporte incluido."""
    op_pl = cargar_plantilla(op_yaml)
    cont_pl = cargar_plantilla(cont_yaml)

    res_op, canon_op = mapear_archivo(op_path, op_pl)
    res_cont, canon_cont = mapear_archivo(cont_path, cont_pl)
    for res, canon in ((res_op, canon_op), (res_cont, canon_cont)):
        if canon is None:
            raise PipelineError(res.report())

    cruce = cruzar(canon_op, canon_cont)
    recon = calcular_brecha(cruce, cargar_umbrales(umbrales_yaml))
    final = calcular_derivada(recon, cargar_factores(factores_yaml))
    return final, [res_op, res_cont]


def plantillas_disponibles() -> dict:
    """Mapa {nombre de archivo: ruta} de las plantillas de mapeo en config/."""
    rutas = sorted(glob.glob(os.path.join(CONFIG, "mapping_*.yaml")))
    return {os.path.basename(r): r for r in rutas}


def guardar_subida(archivo_subido) -> str:
    """Vuelca un archivo subido (Streamlit UploadedFile) a un temporal en disco,
    conservando la extensión, y devuelve la ruta. `engine.ingest` lee por ruta."""
    sufijo = os.path.splitext(archivo_subido.name)[1].lower()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=sufijo)
    tmp.write(archivo_subido.getbuffer())
    tmp.close()
    return tmp.name


def etiqueta_periodo(df) -> str:
    """Etiqueta de período para la metadata: único o rango 'min…max'."""
    periodos = sorted(p for p in df["periodo"].dropna().unique())
    if not periodos:
        return "—"
    return periodos[0] if len(periodos) == 1 else f"{periodos[0]}…{periodos[-1]}"


RUTA_UMBRALES = os.path.join(CONFIG, "umbrales.yaml")
RUTA_FACTORES = os.path.join(CONFIG, "factores.yaml")
RUTA_DB = os.path.join(DATA, "greenclaim.db")


def _asegurar_datos_demo():
    """Genera los CSV de ejemplo si faltan (data/ no está versionado)."""
    op = os.path.join(DATA, "operativo_ejemplo.csv")
    cont = os.path.join(DATA, "contable_ejemplo.csv")
    if not os.path.exists(op):
        subprocess.run([sys.executable, os.path.join(RAIZ, "make_sample_data.py")], check=True)
    if not os.path.exists(cont):
        subprocess.run([sys.executable, os.path.join(RAIZ, "make_sample_contable.py")], check=True)
    return op, cont


def reconciliacion_demo():
    """Reconciliación de ejemplo (datos + plantillas del repo). Devuelve
    ``(df_final, meta)``. Sustituible por la carga real en el paso 8."""
    op, cont = _asegurar_datos_demo()
    final, _avisos = construir_reconciliacion(
        op, os.path.join(CONFIG, "mapping_ejemplo.yaml"),
        cont, os.path.join(CONFIG, "mapping_ejemplo_contable.yaml"),
        RUTA_UMBRALES, RUTA_FACTORES,
    )
    meta = {
        "planta": "Planta Tipo (demo)",
        "periodo": "2025-06",
        "generado_en": date.today().isoformat(),
    }
    return final, meta

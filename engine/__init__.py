"""Motor de GreenClaim (headless, independiente de la UI)."""
from .ingest import ingest, read_file, IngestResult, ValidationIssue
from .mapping import (
    cargar_plantilla,
    aplicar_mapeo,
    mapear_archivo,
    Plantilla,
    PlantillaError,
)
from .cruce import cruzar, CruceError
from .brecha import calcular_brecha, cargar_umbrales, Umbrales, UmbralesError
from .emisiones import (
    calcular_derivada,
    cargar_factores,
    Factor,
    Factores,
    FactoresError,
)
from .export import exportar_excel, COLUMNAS_REPORTE
from .cierre import evaluar_cierre, ResultadoCierre
from . import persistencia

__all__ = [
    "ingest", "read_file", "IngestResult", "ValidationIssue",
    "cargar_plantilla", "aplicar_mapeo", "mapear_archivo",
    "Plantilla", "PlantillaError",
    "cruzar", "CruceError",
    "calcular_brecha", "cargar_umbrales", "Umbrales", "UmbralesError",
    "calcular_derivada", "cargar_factores", "Factor", "Factores", "FactoresError",
    "exportar_excel", "COLUMNAS_REPORTE",
    "evaluar_cierre", "ResultadoCierre", "persistencia",
]

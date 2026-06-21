"""Mapeo al modelo canónico + agregación mensual (paso 2 del MVP).

Traduce las columnas crudas de cada empresa al vocabulario canónico de
GreenClaim y agrega a nivel mensual. Este módulo NO hace cruce ni brecha
(eso es el paso 3): su única responsabilidad es producir una tabla canónica
"larga" con una fila por ``(periodo, energetico, fuente)``.

La traducción se declara en una plantilla YAML por empresa (ver
``config/mapping_ejemplo.yaml``). La lectura y validación estructural del
archivo se delegan en ``engine.ingest`` ANTES de mapear.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

import pandas as pd
import yaml

from engine.ingest import ingest as ingest_archivo
from engine.schema import Energetico, TipoEnergetico, Fuente

# Columnas del DataFrame canónico que produce este módulo.
COLUMNAS_CANONICAS = ["periodo", "energetico", "tipo", "unidad", "fuente", "valor"]

AGREGACIONES_VALIDAS = {"sum", "mean"}

# Tokens cortos admitidos en el YAML → enum canónico. Aceptamos tanto el valor
# del enum como alias cortos (los que usa el modelo canónico del CLAUDE.md),
# para que las plantillas sean legibles sin acoplarlas a los nombres internos.
_ALIAS_TIPO = {
    "fosil": TipoEnergetico.FOSIL,
    "biogenico": TipoEnergetico.BIOGENICO,
    "electricidad_red": TipoEnergetico.ELECTRICIDAD_RED,
}


class PlantillaError(ValueError):
    """La plantilla de mapeo es inválida o está incompleta."""


@dataclass
class EnergeticoMap:
    """Cómo construir un energético canónico desde columnas crudas.

    Si ``columnas`` trae varias, se SUMAN fila a fila (componentes de un mismo
    energético partidos en el PI). Luego se agrega al mes con ``agregacion``.
    """
    energetico: Energetico
    tipo: TipoEnergetico
    unidad: str
    fuente: Fuente
    columnas: list
    agregacion: str = "sum"


@dataclass
class Lectura:
    """Parámetros de lectura del archivo (offset de encabezado por planta)."""
    sheet: Union[int, str] = 0
    header: int = 0
    skiprows: Optional[Union[int, list]] = None


@dataclass
class Identidad:
    """Columnas que identifican una fila cruda. Por ahora solo la fecha."""
    fecha: str


@dataclass
class Plantilla:
    """Plantilla de mapeo declarativa de una empresa/planta."""
    empresa: str
    lectura: Lectura
    identidad: Identidad
    energeticos: list = field(default_factory=list)

    @property
    def columnas_componentes(self) -> list:
        """Todas las columnas crudas referidas por algún energético (sin repetir)."""
        vistas: list = []
        for em in self.energeticos:
            for col in em.columnas:
                if col not in vistas:
                    vistas.append(col)
        return vistas


def _resolver_enum(enum_cls, valor, *, alias=None, campo=""):
    """Resuelve un token del YAML a un miembro de enum. Acepta el valor del
    enum o un alias corto. Lanza PlantillaError con un mensaje claro si no."""
    alias = alias or {}
    if isinstance(valor, str):
        if valor in alias:
            return alias[valor]
        for miembro in enum_cls:
            if miembro.value == valor:
                return miembro
    validos = sorted({m.value for m in enum_cls} | set(alias))
    raise PlantillaError(
        f"Valor inválido para '{campo}': {valor!r}. "
        f"Use uno de: {', '.join(validos)}."
    )


def cargar_plantilla(path: str) -> Plantilla:
    """Lee y valida una plantilla YAML; devuelve un objeto ``Plantilla``.

    Lanza ``PlantillaError`` con un mensaje legible ante cualquier problema
    de estructura o de valores (enums desconocidos, claves faltantes, etc.).
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            cruda = yaml.safe_load(fh)
    except FileNotFoundError as exc:
        raise PlantillaError(f"No existe la plantilla: {path}") from exc
    except yaml.YAMLError as exc:
        raise PlantillaError(f"YAML inválido en {path}: {exc}") from exc

    if not isinstance(cruda, dict):
        raise PlantillaError("La plantilla debe ser un mapa YAML en el nivel superior.")

    # --- lectura ---
    lectura_cruda = cruda.get("lectura") or {}
    if not isinstance(lectura_cruda, dict):
        raise PlantillaError("'lectura' debe ser un mapa (sheet/header/skiprows).")
    lectura = Lectura(
        sheet=lectura_cruda.get("sheet", 0),
        header=lectura_cruda.get("header", 0),
        skiprows=lectura_cruda.get("skiprows"),
    )

    # --- identidad ---
    identidad_cruda = cruda.get("identidad") or {}
    if not isinstance(identidad_cruda, dict) or not identidad_cruda.get("fecha"):
        raise PlantillaError("'identidad.fecha' es obligatorio (nombre de la columna de fecha).")
    identidad = Identidad(fecha=str(identidad_cruda["fecha"]))

    # --- energeticos ---
    energeticos_crudos = cruda.get("energeticos")
    if not isinstance(energeticos_crudos, list) or not energeticos_crudos:
        raise PlantillaError("'energeticos' debe ser una lista con al menos un elemento.")

    energeticos: list = []
    for i, item in enumerate(energeticos_crudos):
        ubic = f"energeticos[{i}]"
        if not isinstance(item, dict):
            raise PlantillaError(f"{ubic} debe ser un mapa.")
        for clave in ("energetico", "tipo", "unidad", "fuente", "columnas"):
            if clave not in item:
                raise PlantillaError(f"{ubic}: falta la clave obligatoria '{clave}'.")

        columnas = item["columnas"]
        if isinstance(columnas, str):
            columnas = [columnas]
        if not isinstance(columnas, list) or not columnas:
            raise PlantillaError(f"{ubic}.columnas debe ser una lista no vacía de nombres de columna.")

        agregacion = item.get("agregacion", "sum")
        if agregacion not in AGREGACIONES_VALIDAS:
            raise PlantillaError(
                f"{ubic}.agregacion inválida: {agregacion!r}. "
                f"Use una de: {', '.join(sorted(AGREGACIONES_VALIDAS))}."
            )

        energeticos.append(EnergeticoMap(
            energetico=_resolver_enum(Energetico, item["energetico"], campo=f"{ubic}.energetico"),
            tipo=_resolver_enum(TipoEnergetico, item["tipo"], alias=_ALIAS_TIPO, campo=f"{ubic}.tipo"),
            unidad=str(item["unidad"]),
            fuente=_resolver_enum(Fuente, item["fuente"], campo=f"{ubic}.fuente"),
            columnas=[str(c) for c in columnas],
            agregacion=agregacion,
        ))

    empresa = str(cruda.get("empresa", "")) or "sin_nombre"
    return Plantilla(empresa=empresa, lectura=lectura, identidad=identidad, energeticos=energeticos)


def aplicar_mapeo(df: pd.DataFrame, plantilla: Plantilla) -> pd.DataFrame:
    """Aplica la plantilla a un DataFrame crudo y devuelve la tabla canónica
    "larga" con columnas ``[periodo, energetico, tipo, unidad, fuente, valor]``.

    Pasos:
      1. ``fecha`` → ``periodo`` mensual (``YYYY-MM``).
      2. suma fila a fila los componentes cuando un energético trae varias columnas.
      3. agrega por ``(periodo, energetico, fuente)`` con la agregación indicada.

    Asume que ``df`` ya pasó la validación estructural de ``engine.ingest``.
    """
    fecha_col = plantilla.identidad.fecha
    faltantes = [c for c in [fecha_col] + plantilla.columnas_componentes if c not in df.columns]
    if faltantes:
        raise PlantillaError(
            "Columnas declaradas en la plantilla que no están en el archivo: "
            + ", ".join(repr(c) for c in faltantes)
        )

    periodo = pd.to_datetime(df[fecha_col], errors="coerce").dt.strftime("%Y-%m")

    bloques: list = []
    for em in plantilla.energeticos:
        # Componentes a numérico y suma fila a fila (min_count=1: todo-NaN → NaN).
        componentes = df[em.columnas].apply(pd.to_numeric, errors="coerce")
        valor_fila = componentes.sum(axis=1, min_count=1)

        tmp = pd.DataFrame({"periodo": periodo, "valor": valor_fila})
        # Descartar filas sin periodo válido (no deberían existir tras la ingesta).
        tmp = tmp.dropna(subset=["periodo"])

        agregado = (
            tmp.groupby("periodo", as_index=False)["valor"]
            .agg(em.agregacion)
        )
        agregado["energetico"] = em.energetico.value
        agregado["tipo"] = em.tipo.value
        agregado["unidad"] = em.unidad
        agregado["fuente"] = em.fuente.value
        bloques.append(agregado)

    canonico = pd.concat(bloques, ignore_index=True)
    canonico = canonico[COLUMNAS_CANONICAS]
    canonico = canonico.sort_values(["periodo", "energetico", "fuente"]).reset_index(drop=True)
    return canonico


def mapear_archivo(path: str, plantilla: Plantilla):
    """Lee y valida un archivo con ``engine.ingest`` y, si es válido, aplica el
    mapeo. Devuelve ``(IngestResult, DataFrame | None)``: el DataFrame canónico
    es ``None`` cuando la ingesta falla (revisa ``resultado.report()``).

    Las columnas obligatorias, de fecha y numéricas se derivan de la plantilla,
    de modo que cada empresa valida exactamente lo que su mapeo necesita.
    """
    fecha_col = plantilla.identidad.fecha
    componentes = plantilla.columnas_componentes
    resultado = ingest_archivo(
        path,
        required_columns=[fecha_col] + componentes,
        date_columns=[fecha_col],
        numeric_columns=componentes,
        sheet=plantilla.lectura.sheet,
        header=plantilla.lectura.header,
        skiprows=plantilla.lectura.skiprows,
    )
    if not resultado.ok or resultado.data is None:
        return resultado, None
    return resultado, aplicar_mapeo(resultado.data, plantilla)

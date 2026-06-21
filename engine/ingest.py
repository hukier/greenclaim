"""Ingesta y validación estructural de archivos de entrada.

Paso 1 del MVP GreenClaim. Este módulo NO conoce energéticos ni reglas de
negocio: solo lee un CSV/XLSX a un DataFrame y comprueba que la estructura
sea utilizable antes de pasarlo al motor. El mapeo al modelo canónico y la
reconciliación llegan en pasos posteriores.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

SUPPORTED_EXT = {".csv", ".xlsx", ".xls"}


@dataclass
class ValidationIssue:
    """Un problema detectado durante la ingesta."""
    level: str       # "error" (bloquea) | "warning" (solo advierte)
    code: str        # identificador estable, ej. "missing_column"
    message: str     # texto legible para el usuario

    def __str__(self) -> str:
        marca = "✗" if self.level == "error" else "!"
        return f"  {marca} [{self.code}] {self.message}"


@dataclass
class IngestResult:
    """Resultado de ingerir un archivo: estado, datos y problemas."""
    ok: bool
    source: str
    rows: int
    columns: list
    issues: list = field(default_factory=list)
    preview: Optional[pd.DataFrame] = None
    data: Optional[pd.DataFrame] = None

    @property
    def errors(self) -> list:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list:
        return [i for i in self.issues if i.level == "warning"]

    def report(self) -> str:
        estado = "OK" if self.ok else "RECHAZADO"
        lineas = [f"[{estado}] {os.path.basename(self.source)}  ·  "
                  f"{self.rows} filas · {len(self.columns)} columnas"]
        if self.issues:
            for issue in self.issues:
                lineas.append(str(issue))
        else:
            lineas.append("  Sin observaciones.")
        return "\n".join(lineas)


def read_file(path: str, *, sheet=0, header: int = 0, skiprows=None) -> pd.DataFrame:
    """Lee un CSV o XLSX a DataFrame. `header` es el índice (0-based) de la
    fila que contiene los nombres de columna; útil cuando el archivo trae
    filas de título o metadatos arriba. `skiprows` (int o lista de índices
    0-based del archivo original) descarta filas adicionales, p. ej. la fila
    de unidades que algunos exports colocan justo bajo el encabezado."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return pd.read_csv(path, header=header, skiprows=skiprows)
    return pd.read_excel(path, sheet_name=sheet, header=header, skiprows=skiprows)


def ingest(
    path: str,
    *,
    required_columns: Optional[list] = None,
    date_columns: Optional[list] = None,
    numeric_columns: Optional[list] = None,
    sheet=0,
    header: int = 0,
    skiprows=None,
    preview_rows: int = 5,
) -> IngestResult:
    """Lee un archivo y corre las validaciones estructurales del MVP.

    Validaciones (un fallo de nivel ``error`` deja ``ok=False``):
      1. el archivo existe
      2. la extensión está admitida (.csv, .xlsx, .xls)
      3. el archivo no está vacío
      4. están presentes las columnas obligatorias
      5. las fechas se pueden parsear
      6. las columnas numéricas no contienen texto
    Los datos faltantes en columnas numéricas generan solo una advertencia.
    """
    required_columns = required_columns or []
    date_columns = date_columns or []
    numeric_columns = numeric_columns or []
    issues: list = []

    # 1. existencia
    if not os.path.exists(path):
        return IngestResult(False, path, 0, [],
                            [ValidationIssue("error", "missing_file",
                                             f"No existe el archivo: {path}")])

    # 2. formato admitido
    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_EXT:
        return IngestResult(False, path, 0, [],
                            [ValidationIssue("error", "bad_format",
                                             f"Formato no admitido: '{ext}'. "
                                             f"Use CSV o XLSX.")])

    # lectura
    try:
        df = read_file(path, sheet=sheet, header=header, skiprows=skiprows)
    except Exception as exc:  # noqa: BLE001  (queremos reportar cualquier fallo de lectura)
        return IngestResult(False, path, 0, [],
                            [ValidationIssue("error", "read_error",
                                             f"No se pudo leer el archivo: {exc}")])

    cols = list(df.columns)

    # 3. archivo vacío
    if df.empty:
        issues.append(ValidationIssue("error", "empty_file",
                                      "El archivo no contiene filas de datos."))

    # 4. columnas obligatorias
    for col in required_columns:
        if col not in cols:
            issues.append(ValidationIssue("error", "missing_column",
                                          f"Falta la columna obligatoria: '{col}'."))

    # 5. fechas parseables
    for col in date_columns:
        if col in cols:
            parsed = pd.to_datetime(df[col], errors="coerce")
            invalidas = int(parsed.isna().sum() - df[col].isna().sum())
            if invalidas > 0:
                issues.append(ValidationIssue("error", "bad_date",
                                              f"{invalidas} fecha(s) inválida(s) en '{col}'."))

    # 6. numéricos + datos faltantes
    for col in numeric_columns:
        if col in cols:
            coerced = pd.to_numeric(df[col], errors="coerce")
            no_numericos = int(coerced.isna().sum() - df[col].isna().sum())
            if no_numericos > 0:
                issues.append(ValidationIssue("error", "non_numeric",
                                              f"{no_numericos} valor(es) no numérico(s) en '{col}'."))
            faltantes = int(df[col].isna().sum())
            if faltantes > 0:
                issues.append(ValidationIssue("warning", "missing_values",
                                              f"{faltantes} dato(s) faltante(s) en '{col}'."))

    ok = not any(i.level == "error" for i in issues)
    return IngestResult(ok, path, len(df), cols, issues,
                        preview=df.head(preview_rows), data=df)

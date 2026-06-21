"""Brecha + estado por umbral (paso 4 del MVP).

Sobre la tabla de cruce del paso 3
(``[periodo, energetico, tipo, unidad, valor_op, valor_cont]``) calcula la
brecha en **unidad nativa** y asigna el estado según el umbral por energético:

    [..., brecha_abs, brecha_pct, estado]

Reglas (ver CLAUDE.md):
  - ``brecha_abs  = valor_op − valor_cont``
  - ``brecha_pct  = brecha_abs / valor_cont × 100``  (NaN si no es calculable)
  - estado:
      * ``pendiente``  si falta un lado (NaN) o hay un valor 0 por mantención;
      * ``cuadrado``   si ``|brecha_pct| ≤ umbral`` del energético;
      * ``desviacion`` si lo supera.

Los umbrales son **provisionales y configurables** (YAML): no se cablean aquí.
Este módulo NO decide cierre ni justificación (flujo posterior); solo el estado.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
import yaml

from engine.cruce import COLUMNAS_CRUCE
from engine.schema import Estado

# Columnas que este paso añade a la tabla de cruce.
COLUMNAS_BRECHA = ["brecha_abs", "brecha_pct", "estado"]


class UmbralesError(ValueError):
    """El archivo de umbrales es inválido o está incompleto."""


@dataclass
class Umbrales:
    """Umbrales de brecha (en %) por energético, con respaldo opcional."""
    por_energetico: dict = field(default_factory=dict)
    default: Optional[float] = None

    def para(self, energetico: str) -> Optional[float]:
        """Umbral (%) del energético, o el ``default`` si no está declarado.
        Devuelve ``None`` si no hay umbral aplicable."""
        if energetico in self.por_energetico:
            return self.por_energetico[energetico]
        return self.default


def cargar_umbrales(path: str) -> Umbrales:
    """Lee y valida el YAML de umbrales; devuelve un objeto ``Umbrales``.

    Lanza ``UmbralesError`` con mensaje claro ante problemas de estructura o
    valores no numéricos / negativos.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            cruda = yaml.safe_load(fh)
    except FileNotFoundError as exc:
        raise UmbralesError(f"No existe el archivo de umbrales: {path}") from exc
    except yaml.YAMLError as exc:
        raise UmbralesError(f"YAML inválido en {path}: {exc}") from exc

    if not isinstance(cruda, dict):
        raise UmbralesError("El archivo de umbrales debe ser un mapa YAML.")

    por_energetico_crudo = cruda.get("energeticos") or {}
    if not isinstance(por_energetico_crudo, dict):
        raise UmbralesError("'energeticos' debe ser un mapa {energetico: umbral}.")

    def _num(valor, donde):
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise UmbralesError(f"Umbral no numérico en {donde}: {valor!r}.")
        if valor < 0:
            raise UmbralesError(f"Umbral negativo en {donde}: {valor!r}.")
        return float(valor)

    por_energetico = {
        str(k): _num(v, f"energeticos.{k}")
        for k, v in por_energetico_crudo.items()
    }

    default = cruda.get("default")
    if default is not None:
        default = _num(default, "default")

    if not por_energetico and default is None:
        raise UmbralesError("No hay ningún umbral declarado (ni por energético ni default).")

    return Umbrales(por_energetico=por_energetico, default=default)


def calcular_brecha(cruce: pd.DataFrame, umbrales: Umbrales) -> pd.DataFrame:
    """Añade ``[brecha_abs, brecha_pct, estado]`` a la tabla de cruce.

    Asume que ``cruce`` viene de ``engine.cruce.cruzar`` (columnas
    ``COLUMNAS_CRUCE``). No muta el DataFrame de entrada.
    """
    faltantes = [c for c in COLUMNAS_CRUCE if c not in cruce.columns]
    if faltantes:
        raise ValueError(
            "La tabla no tiene formato de cruce; faltan columnas: "
            + ", ".join(repr(c) for c in faltantes)
        )

    out = cruce.copy()
    op = pd.to_numeric(out["valor_op"], errors="coerce")
    cont = pd.to_numeric(out["valor_cont"], errors="coerce")

    out["brecha_abs"] = op - cont
    # brecha_pct solo si valor_cont es válido y distinto de 0; donde no, queda NaN
    # (el .where descarta tanto el 0/0 → NaN como el x/0 → inf).
    pct = (out["brecha_abs"] / cont) * 100
    out["brecha_pct"] = pct.where(cont.notna() & (cont != 0))

    out["estado"] = [
        _estado_fila(o, c, out.at[i, "brecha_pct"],
                     umbrales.para(out.at[i, "energetico"]))
        for i, (o, c) in enumerate(zip(op, cont))
    ]
    return out


def _estado_fila(valor_op, valor_cont, brecha_pct, umbral) -> str:
    """Decide el estado de una fila. 'pendiente' tiene prioridad: falta un lado
    o hay un valor 0 (típicamente mantención). Si ambos lados son válidos y no
    nulos, compara |brecha_pct| contra el umbral."""
    falta_lado = pd.isna(valor_op) or pd.isna(valor_cont)
    valor_cero = (valor_op == 0) or (valor_cont == 0)
    if falta_lado or valor_cero:
        return Estado.PENDIENTE.value
    # Sin umbral aplicable o brecha no calculable → no se puede afirmar cuadrado.
    if umbral is None or pd.isna(brecha_pct):
        return Estado.PENDIENTE.value
    if abs(brecha_pct) <= umbral:
        return Estado.CUADRADO.value
    return Estado.DESVIACION.value

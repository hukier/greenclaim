"""Capa derivada: energía (GJ) + emisiones (tCO₂eq) (paso 5 del MVP).

Capa OPCIONAL sobre la tabla de reconciliación del paso 4. Es derivada y NO
bloquea el núcleo: si faltan factores (o son cero), las columnas derivadas
quedan en ``NaN`` (con un *warning*, no un error) y la brecha/estado del paso 4
siguen siendo válidas.

Añade tres columnas, usando el lado **operativo** como base:
  - ``energia_gj        = valor_op * factor_gj``
  - ``emisiones_tco2eq  = energia_gj * factor_co2``  (0 para biogénico)
  - ``es_biogenico``    : bool, para separar lo biogénico en el reporte

Los factores son **provisionales y configurables** (YAML): no se cablean aquí.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import yaml

# Columnas que este paso añade a la tabla del paso 4.
COLUMNAS_DERIVADA = ["energia_gj", "emisiones_tco2eq", "es_biogenico"]


class FactoresError(ValueError):
    """El archivo de factores es inválido o está incompleto."""


@dataclass
class Factor:
    """Factores derivados de un energético."""
    factor_gj: float
    factor_co2: float
    biogenico: bool = False


@dataclass
class Factores:
    """Factores por energético, con respaldo opcional (``default``)."""
    por_energetico: dict
    default: Optional[Factor] = None

    def para(self, energetico: str) -> Optional[Factor]:
        """Factor del energético, o el ``default`` si no está declarado.
        Devuelve ``None`` si no hay factor aplicable (→ derivados en NaN)."""
        if energetico in self.por_energetico:
            return self.por_energetico[energetico]
        return self.default


def _num_no_negativo(valor, donde: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise FactoresError(f"Factor no numérico en {donde}: {valor!r}.")
    if valor < 0:
        raise FactoresError(f"Factor negativo en {donde}: {valor!r}.")
    return float(valor)


def _parsear_factor(crudo, donde: str) -> Factor:
    if not isinstance(crudo, dict):
        raise FactoresError(f"{donde} debe ser un mapa con factor_gj y factor_co2.")
    for campo in ("factor_gj", "factor_co2"):
        if campo not in crudo:
            raise FactoresError(f"{donde}: falta el campo obligatorio '{campo}'.")
    biogenico = crudo.get("biogenico", False)
    if not isinstance(biogenico, bool):
        raise FactoresError(f"{donde}.biogenico debe ser true/false, no {biogenico!r}.")
    return Factor(
        factor_gj=_num_no_negativo(crudo["factor_gj"], f"{donde}.factor_gj"),
        factor_co2=_num_no_negativo(crudo["factor_co2"], f"{donde}.factor_co2"),
        biogenico=biogenico,
    )


def cargar_factores(path: str) -> Factores:
    """Lee y valida el YAML de factores; devuelve un objeto ``Factores``.

    Lanza ``FactoresError`` con mensaje claro ante problemas de estructura,
    campos faltantes o valores no numéricos / negativos.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            cruda = yaml.safe_load(fh)
    except FileNotFoundError as exc:
        raise FactoresError(f"No existe el archivo de factores: {path}") from exc
    except yaml.YAMLError as exc:
        raise FactoresError(f"YAML inválido en {path}: {exc}") from exc

    if not isinstance(cruda, dict):
        raise FactoresError("El archivo de factores debe ser un mapa YAML.")

    por_energetico_crudo = cruda.get("energeticos") or {}
    if not isinstance(por_energetico_crudo, dict):
        raise FactoresError("'energeticos' debe ser un mapa {energetico: {factores}}.")

    por_energetico = {
        str(k): _parsear_factor(v, f"energeticos.{k}")
        for k, v in por_energetico_crudo.items()
    }

    default_crudo = cruda.get("default")
    default = _parsear_factor(default_crudo, "default") if default_crudo is not None else None

    if not por_energetico and default is None:
        raise FactoresError("No hay ningún factor declarado (ni por energético ni default).")

    return Factores(por_energetico=por_energetico, default=default)


def calcular_derivada(df_brecha: pd.DataFrame, factores: Factores) -> pd.DataFrame:
    """Añade ``[energia_gj, emisiones_tco2eq, es_biogenico]`` a la tabla del
    paso 4. No muta la entrada.

    Si un energético no tiene factor aplicable, sus derivados quedan en ``NaN``
    y se emite un *warning* (no un error): la capa es opcional.
    """
    for col in ("energetico", "valor_op"):
        if col not in df_brecha.columns:
            raise ValueError(f"Falta la columna '{col}' requerida para la capa derivada.")

    out = df_brecha.copy()
    energ = out["energetico"]

    resueltos = {e: factores.para(e) for e in energ.unique()}
    sin_factor = sorted(e for e, f in resueltos.items() if f is None)
    if sin_factor:
        warnings.warn(
            "Sin factor para: " + ", ".join(sin_factor)
            + ". Energía y emisiones quedan en NaN para esos energéticos.",
            UserWarning,
            stacklevel=2,
        )

    factor_gj = energ.map(lambda e: resueltos[e].factor_gj if resueltos[e] else np.nan)
    factor_co2 = energ.map(lambda e: resueltos[e].factor_co2 if resueltos[e] else np.nan)
    es_bio = energ.map(lambda e: bool(resueltos[e].biogenico) if resueltos[e] else False)

    valor_op = pd.to_numeric(out["valor_op"], errors="coerce")
    out["energia_gj"] = valor_op * factor_gj

    emisiones = out["energia_gj"] * factor_co2
    # Biogénico: emisiones fósiles = 0 (sin pisar los NaN de energía desconocida).
    emisiones = emisiones.mask(es_bio & out["energia_gj"].notna(), 0.0)
    out["emisiones_tco2eq"] = emisiones
    out["es_biogenico"] = es_bio
    return out

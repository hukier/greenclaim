"""GreenClaim — UI Streamlit.

Rediseño "Cuadratura mensual": barra superior de marca, fila de KPIs reales,
tabla de fuentes con pills de estado y acción de auditoría por fila (justificar
vía diálogo), cierre y exportación del borrador.

La lógica de negocio vive en `engine`; aquí solo se presenta. El look usa CSS/
HTML propio (pedido explícito) además del tema de `.streamlit/config.toml`.
Ejecutar:
    streamlit run ui/app.py
"""
import io
import os
import sys
from datetime import date

import pandas as pd
import streamlit as st

# `streamlit run ui/app.py` agrega ui/ al path; AppTest/otros invocadores no.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import (  # noqa: E402  (pipeline pone engine en path)
    reconciliacion_demo,
    construir_reconciliacion,
    plantillas_disponibles,
    guardar_subida,
    etiqueta_periodo,
    PipelineError,
    RUTA_UMBRALES,
    RUTA_FACTORES,
    RUTA_DB,
)
from engine.export import exportar_excel, COLUMNAS_REPORTE  # noqa: E402
from engine.cierre import evaluar_cierre  # noqa: E402
from engine import persistencia as pe  # noqa: E402

# Etiquetas legibles para la columna EQUIPO / RECURSO.
NOMBRE_ENERGETICO = {
    "gas_natural": "Gas natural",
    "diesel": "Diésel",
    "fuel_oil": "Fuel oil",
    "biomasa": "Biomasa",
    "electricidad_comprada": "Electricidad (red)",
}
NOMBRE_TIPO = {
    "fosil": "Fósil",
    "biogenico": "Biogénico",
    "electricidad_red": "Red eléctrica",
}

# Proporciones de las columnas de la "tabla" (st.columns por fila).
RATIOS = [3, 2, 2, 1.5, 2, 2]

st.set_page_config(
    page_title="GreenClaim — Cuadratura mensual",
    page_icon=":material/eco:",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ----------------------------------------------------------------------------
# Estilos (CSS/HTML propio — solicitado explícitamente para barra/pills/tabla).
# ----------------------------------------------------------------------------
def inyectar_estilos():
    st.html(
        """
        <style>
          /* Se deja el header nativo de Streamlit intacto (ahí vive el control
             para abrir/cerrar la barra lateral). Solo bajamos el contenido para
             que el botón Deploy no tape la barra verde de marca. */
          .block-container { padding-top: 4rem; max-width: 1200px; }

          /* Barra superior de marca. */
          .gc-topbar {
            display:flex; justify-content:space-between; align-items:center;
            background:#0F3D2E; color:#fff; padding:14px 24px;
            border-radius:12px; margin-bottom:22px;
          }
          .gc-brand { display:flex; align-items:center; gap:12px; }
          .gc-logo { font-weight:700; font-size:18px; letter-spacing:-.01em; }
          .gc-badge-corp {
            font-size:11px; letter-spacing:.10em; font-weight:600;
            background:rgba(255,255,255,.14); color:#BFE3CC;
            padding:3px 9px; border-radius:6px;
          }
          .gc-user { display:flex; align-items:center; gap:12px;
            font-size:14px; color:#CDE9D6; }
          .gc-avatar {
            background:#15803D; color:#fff; width:34px; height:34px;
            border-radius:50%; display:flex; align-items:center;
            justify-content:center; font-weight:600; font-size:13px;
          }

          /* Título de dos tonos. */
          .gc-title { font-size:30px; font-weight:700; letter-spacing:-.02em;
            color:#16261B; margin:0; }
          .gc-title span { color:#9AA69E; font-weight:500; }

          /* Encabezados de la tabla y celdas auxiliares. */
          .gc-th { font-size:11px; letter-spacing:.06em; font-weight:600;
            color:#8A968D; text-transform:uppercase; }
          .gc-th small { font-weight:400; text-transform:none; letter-spacing:0; }
          .gc-equipo { font-weight:600; color:#16261B; line-height:1.2; }
          .gc-recurso { font-size:12px; color:#8A968D; }
          .gc-valor { font-weight:600; color:#16261B; }
          .gc-valor small { font-weight:400; color:#8A968D; }
          .gc-revisado { color:#9AA69E; font-size:13px; }
        </style>
        """
    )


def barra_superior(planta):
    st.html(
        f"""
        <div class="gc-topbar">
          <div class="gc-brand">
            <span class="gc-logo">🌿 GreenClaim</span>
            <span class="gc-badge-corp">CORPORATIVO</span>
          </div>
          <div class="gc-user">
            <span>{planta}</span>
            <span class="gc-avatar">{_iniciales(planta)}</span>
          </div>
        </div>
        """
    )


def _iniciales(texto):
    palabras = [p for p in str(texto).split() if p[:1].isalnum()]
    if not palabras:
        return "··"
    if len(palabras) == 1:
        return palabras[0][:2].upper()
    return (palabras[0][0] + palabras[1][0]).upper()


# ----------------------------------------------------------------------------
# Carga de datos (sidebar) — sin cambios de lógica.
# ----------------------------------------------------------------------------
@st.cache_data
def cargar_demo():
    return reconciliacion_demo()


def mostrar_avisos(avisos):
    for res in avisos:
        nombre = os.path.basename(res.source)
        if res.warnings:
            with st.expander(f":material/info: Validación: {nombre} "
                             f"({len(res.warnings)} aviso/s)"):
                st.text(res.report())


def panel_fuentes():
    """Sidebar: elegir origen de datos. Devuelve (final, meta, avisos) o None."""
    st.sidebar.header(":material/database: Fuentes de datos")
    modo = st.sidebar.radio(
        "Origen", ["Datos de ejemplo", "Subir archivos"],
        captions=["Demo del repo", "Operativo + contable"],
    )

    if modo == "Datos de ejemplo":
        final, meta = cargar_demo()
        return final, meta, []

    plantillas = plantillas_disponibles()
    nombres = list(plantillas)
    st.sidebar.caption("Subí los dos archivos y elegí su plantilla de mapeo.")
    planta = st.sidebar.text_input("Nombre de la planta", value="Sin nombre")

    op_file = st.sidebar.file_uploader("Archivo operativo (PI)", type=["csv", "xlsx", "xls"])
    op_yaml = st.sidebar.selectbox(
        "Plantilla operativo", nombres,
        index=nombres.index("mapping_ejemplo.yaml") if "mapping_ejemplo.yaml" in nombres else 0,
    )
    cont_file = st.sidebar.file_uploader("Archivo contable (SAP)", type=["csv", "xlsx", "xls"])
    cont_yaml = st.sidebar.selectbox(
        "Plantilla contable", nombres,
        index=(nombres.index("mapping_ejemplo_contable.yaml")
               if "mapping_ejemplo_contable.yaml" in nombres else 0),
    )

    if not (op_file and cont_file):
        st.info("Subí ambos archivos en el panel lateral para reconciliar.",
                icon=":material/upload:")
        return None

    try:
        final, avisos = construir_reconciliacion(
            guardar_subida(op_file), plantillas[op_yaml],
            guardar_subida(cont_file), plantillas[cont_yaml],
            RUTA_UMBRALES, RUTA_FACTORES,
        )
    except PipelineError as exc:
        st.error("La ingesta de un archivo falló:", icon=":material/error:")
        st.text(str(exc))
        return None
    except Exception as exc:  # noqa: BLE001
        st.error(f"No se pudo reconciliar: {exc}", icon=":material/error:")
        return None

    meta = {"planta": planta or "Sin nombre",
            "periodo": etiqueta_periodo(final),
            "generado_en": date.today().isoformat()}
    return final, meta, avisos


# ----------------------------------------------------------------------------
# KPIs reales (sin deltas inventados).
# ----------------------------------------------------------------------------
def fila_kpis(final):
    total = len(final)
    cuadrados = int((final["estado"] == "cuadrado").sum())
    pct = final["brecha_pct"].abs()
    desv_prom = pct.dropna().mean() if pct.notna().any() else 0.0
    energia = final["energia_gj"].sum(min_count=1)
    energia = 0.0 if pd.isna(energia) else energia

    with st.container(horizontal=True):
        st.metric("Líneas cuadradas", f"{cuadrados}/{total}",
                  help="Energéticos cuadrados sobre el total del período.", border=True)
        st.metric("Desviación promedio", f"{desv_prom:.1f} %",
                  help="Promedio del valor absoluto de la brecha porcentual.", border=True)
        st.metric("Energía total", f"{energia:,.0f} GJ",
                  help="Suma de energía operativa convertida a GJ.", border=True)


# ----------------------------------------------------------------------------
# Tabla de fuentes (filas con st.columns + pills + acción de auditoría).
# ----------------------------------------------------------------------------
@st.dialog("Justificar dato")
def _dialogo_justificar(planta, periodo, energetico, etiqueta, actual):
    st.markdown(f"**{etiqueta}** · {periodo}")
    st.caption("La nota queda registrada con fecha y habilita el cierre de la desviación.")
    nota = st.text_area("Nota de justificación", value=actual or "")
    if st.button("Guardar justificación", type="primary", icon=":material/save:"):
        conn = pe.conectar(RUTA_DB)
        una = pd.DataFrame([{"periodo": periodo, "energetico": energetico,
                             "justificacion": nota}])
        pe.guardar_justificaciones(conn, planta, una)
        conn.close()
        st.toast(f"{etiqueta} justificada y guardada.", icon=":material/check_circle:")
        st.rerun()


def _encabezado_tabla():
    cols = st.columns(RATIOS, vertical_alignment="bottom")
    etiquetas = [
        "Equipo / recurso",
        "Operaciones<br><small>(sensores)</small>",
        "Contabilidad<br><small>(facturas)</small>",
        "Brecha", "Estado", "Acción de auditoría",
    ]
    for col, txt in zip(cols, etiquetas):
        col.html(f"<span class='gc-th'>{txt}</span>")


def _fmt_valor(v, unidad):
    if pd.isna(v):
        return "—"
    return f"<span class='gc-valor'>{v:,.0f} <small>{unidad}</small></span>"


def _fila(final, planta, fila, i):
    cols = st.columns(RATIOS, vertical_alignment="center")
    estado = fila["estado"]
    nombre = NOMBRE_ENERGETICO.get(fila["energetico"], fila["energetico"])
    recurso = NOMBRE_TIPO.get(fila["tipo"], fila["tipo"])
    justificada = bool(str(fila.get("justificacion") or "").strip())

    cols[0].html(f"<div class='gc-equipo'>{nombre}</div>"
                 f"<div class='gc-recurso'>{recurso}</div>")
    cols[1].html(_fmt_valor(fila["valor_op"], fila["unidad"]))
    cols[2].html(_fmt_valor(fila["valor_cont"], fila["unidad"]))

    # Brecha (roja si es desviación sin justificar).
    pct = fila["brecha_pct"]
    if pd.isna(pct):
        cols[3].markdown("—")
    elif estado == "desviacion" and not justificada:
        cols[3].markdown(f":red[**{pct:.1f}%**]")
    else:
        cols[3].markdown(f"{pct:.1f}%")

    # Pill de estado.
    with cols[4]:
        if estado == "cuadrado":
            st.badge("Cuadrado", icon=":material/check_circle:", color="green")
        elif estado == "desviacion" and justificada:
            st.badge("Justificada", icon=":material/verified:", color="green")
        elif estado == "desviacion":
            st.badge("Desviación", icon=":material/error:", color="red")
        else:
            st.badge("Pendiente", icon=":material/pending:", color="orange")

    # Acción de auditoría.
    with cols[5]:
        if estado == "cuadrado" or (estado == "desviacion" and justificada):
            st.html("<span class='gc-revisado'>✓ Revisado</span>")
        else:
            if st.button("Justificar dato", key=f"just_{i}", icon=":material/edit:"):
                _dialogo_justificar(planta, fila["periodo"], fila["energetico"],
                                    nombre, fila.get("justificacion"))


def tabla_fuentes(final, planta):
    with st.container(border=True):
        cab, filtro = st.columns([3, 2], vertical_alignment="center")
        cab.subheader("Fuentes fijas a declarar")
        opciones = ["Todos", "Cuadrado", "Desviación", "Pendiente"]
        sel = filtro.segmented_control(
            "Filtro de estado", opciones, default="Todos",
            selection_mode="single", label_visibility="collapsed",
        ) or "Todos"

        mapa = {"Cuadrado": "cuadrado", "Desviación": "desviacion", "Pendiente": "pendiente"}
        vista = final if sel == "Todos" else final[final["estado"] == mapa[sel]]

        _encabezado_tabla()
        if vista.empty:
            st.caption("No hay filas para este filtro.")
            return
        for i, (_, fila) in enumerate(vista.iterrows()):
            _fila(final, planta, fila, i)


# ----------------------------------------------------------------------------
# Cierre del período.
# ----------------------------------------------------------------------------
def seccion_cierre(conn, final, meta):
    with st.container(border=True):
        st.subheader(":material/lock: Cierre del período")
        cerrado = pe.estado_cierre(conn, meta["planta"], meta["periodo"])
        veredicto = evaluar_cierre(final)

        for adv in veredicto.advertencias:
            st.caption(f":material/info: {adv}")

        if cerrado:
            st.success(f"Período cerrado el {cerrado}.", icon=":material/lock:")
            if st.button("Reabrir período", icon=":material/lock_open:"):
                pe.anular_cierre(conn, meta["planta"], meta["periodo"])
                st.rerun()
            return

        if veredicto.puede_cerrar:
            if st.button("Cerrar período", type="primary", icon=":material/lock:"):
                fecha = pe.registrar_cierre(conn, meta["planta"], meta["periodo"])
                st.success(f"Período cerrado el {fecha}.", icon=":material/check_circle:")
                st.rerun()
        else:
            st.error("No se puede cerrar todavía:", icon=":material/block:")
            for bloqueo in veredicto.bloqueos:
                st.markdown(f"- {bloqueo}")


# ----------------------------------------------------------------------------
# Vista principal.
# ----------------------------------------------------------------------------
def con_justificacion(df):
    df = df.copy()
    if "justificacion" not in df.columns:
        df["justificacion"] = ""
    return df[COLUMNAS_REPORTE]


def boton_exportar(final, meta):
    buffer = io.BytesIO()
    exportar_excel(final, meta, buffer)
    buffer.seek(0)
    st.download_button(
        "Exportar borrador", data=buffer,
        file_name=f"borrador_{meta['periodo']}.xlsx".replace("…", "_"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/download:", type="primary",
    )


def mostrar_reconciliacion(final, meta, avisos):
    final = con_justificacion(final)
    conn = pe.conectar(RUTA_DB)
    final = pe.aplicar_justificaciones(final, pe.cargar_justificaciones(conn, meta["planta"]))

    inyectar_estilos()
    barra_superior(meta["planta"])

    titulo, accion = st.columns([3, 1], vertical_alignment="center")
    titulo.html(f"<div class='gc-title'>Cuadratura mensual "
                f"<span>/ {meta['periodo']}</span></div>")
    titulo.caption("Sincroniza datos de sensores (PI) con facturación (SAP) antes de declarar.")
    with accion:
        boton_exportar(final, meta)

    mostrar_avisos(avisos)
    fila_kpis(final)

    sin_justificar = int(((final["estado"] == "desviacion") &
                          (final["justificacion"].astype(str).str.strip() == "")).sum())
    if sin_justificar:
        st.warning(f"{sin_justificar} desviación(es) sin justificar — requieren nota para cerrar.",
                   icon=":material/warning:")

    tabla_fuentes(final, meta["planta"])
    seccion_cierre(conn, final, meta)
    conn.close()


resultado = panel_fuentes()
if resultado is None:
    st.stop()
mostrar_reconciliacion(*resultado)

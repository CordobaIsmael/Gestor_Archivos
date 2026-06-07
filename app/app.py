import streamlit as st
import requests
import pandas as pd
from pathlib import Path

import sys
from pathlib import Path

# Add project root to sys.path to enable config imports
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from config.settings import settings
from ui_components import (
    inject_custom_css, 
    render_header, 
    render_stats, 
    render_reparto_row
)

# Configuration
st.set_page_config(
    page_title="GestorArchivo - Dashboard",
    page_icon="📁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject CSS styles
inject_custom_css()

# Render branding
render_header()

API_URL = settings.API_URL

def force_rerun():
    """Forces streamlit to refresh the dashboard."""
    st.rerun()

@st.dialog("Confirmar Cierre de Caja")
def close_caja_dialog(codigo_caja: str):
    st.warning(f"⚠️ Estás por archivar la **{codigo_caja}** de forma definitiva.")
    st.write("¿La caja ya está llena y realmente deseas cerrarla para archivarla definitivamente?")
    st.info("Al hacerlo, se generará la etiqueta en Word (.docx) y se abrirá automáticamente.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Sí, cerrar y archivar", use_container_width=True):
            try:
                res_close = requests.post(f"{API_URL}/api/cajas/active/close")
                if res_close.status_code == 200:
                    st.toast(f"Caja {codigo_caja} archivada y etiqueta abierta en Word.")
                    st.rerun()
                else:
                    st.error(res_close.json().get("detail", "Error al cerrar."))
            except Exception as ex:
                st.error(f"Error de conexión: {ex}")
    with col2:
        if st.button("No, cancelar", use_container_width=True):
            st.rerun()

# Fetch records from database (via API)
all_repartos = []
active_caja = None
try:
    res = requests.get(f"{API_URL}/api/repartos")
    if res.status_code == 200:
        all_repartos = res.json()
    else:
        st.error("Error al cargar datos desde el backend.")
        
    res_caja = requests.get(f"{API_URL}/api/cajas/active")
    if res_caja.status_code == 200:
        active_caja = res_caja.json()
except Exception as e:
    st.warning("El servidor backend no está respondiendo. Por favor, asegúrate de que el backend esté iniciado.")
    st.info("Puedes iniciar el servidor backend ejecutando el archivo `launcher.py` en tu terminal.")

# Sidebar controls
st.sidebar.markdown("### ⚙️ Panel de Operaciones")
st.sidebar.info(
    "Este sistema escanea la carpeta especificada para digitalizar y organizar automáticamente "
    "las carpetas según su **Hoja de Reparto**."
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📂 Selección de Carpeta")

# Text input to choose folder to scan
scan_path = st.sidebar.text_input(
    "Carpeta a escanear:",
    value=str(settings.ENTRADA),
    help="Ingresa la ruta absoluta de la carpeta a procesar de forma recursiva."
)

st.sidebar.markdown(f"**Salida:** `{settings.SALIDA}`")
st.sidebar.markdown(f"**Revisión:** `{settings.REVISION}`")
st.sidebar.markdown("---")

# Process button in sidebar
if active_caja is None:
    st.sidebar.warning("⚠️ Debes abrir una caja activa para poder procesar la entrada.")

if st.sidebar.button("🔍 Procesar Entrada", use_container_width=True, disabled=active_caja is None):
    if not scan_path.strip():
        st.sidebar.error("Por favor ingresa una ruta válida.")
    else:
        with st.spinner("Escaneando y organizando documentos..."):
            try:
                payload = {"path": scan_path.strip()}
                res = requests.post(f"{API_URL}/api/process", json=payload)
                if res.status_code == 200:
                    data = res.json().get("data", {})
                    organizados = data.get("organizados", [])
                    revision = data.get("revision", [])
                    
                    st.sidebar.success("Escaneo completado.")
                    
                    if organizados or revision:
                        st.toast(f"Procesados: {len(organizados)} organizados, {len(revision)} a revisión.")
                    else:
                        st.toast("No se encontraron carpetas nuevas con PDFs.")
                else:
                    st.sidebar.error(f"Error: {res.json().get('detail', 'Error desconocido')}")
            except Exception as e:
                st.sidebar.error(f"No se pudo conectar al servidor backend: {e}")

st.sidebar.markdown("---")
st.sidebar.markdown("### 📦 Cajas de Archivo Físico")

if active_caja:
    st.sidebar.success(f"**Caja Activa:** `{active_caja['codigo']}`")
    if st.sidebar.button("🔒 Cerrar Caja Activa", use_container_width=True):
        close_caja_dialog(active_caja['codigo'])
else:
    st.sidebar.info("No hay una caja activa abierta. Los repartos procesados no tendrán caja asignada.")
    if st.sidebar.button("➕ Abrir Nueva Caja", use_container_width=True):
        try:
            res_new = requests.post(f"{API_URL}/api/cajas/new", json={})
            if res_new.status_code == 200:
                caja_data = res_new.json().get("data", {})
                codigo_caja = caja_data.get("codigo", "N/A")
                st.toast(f"Caja {codigo_caja} abierta con éxito.")
                st.rerun()
            else:
                st.sidebar.error(res_new.json().get("detail", "Error al abrir la caja."))
        except Exception as ex:
            st.sidebar.error(f"Error de conexión: {ex}")

# Split by state
organizados = [r for r in all_repartos if r["estado"] == "ORGANIZADO"]
en_revision = [r for r in all_repartos if r["estado"] == "EN_REVISION"]

# Display stats cards
render_stats(len(organizados), len(en_revision))

# Tabs layout
tab_revision, tab_search, tab_organizados = st.tabs([
    f"⚠️ En Revisión ({len(en_revision)})", 
    "🔍 Buscar Reparto",
    f"✓ Organizados ({len(organizados)})"
])

with tab_revision:
    st.markdown("### 🛠️ Carpetas Pendientes de Identificación")
    st.markdown(
        "Las siguientes carpetas no contenían una **Hoja de Reparto** identificable o les faltaban "
        "metadatos críticos. Ingrese los datos manualmente para moverlas a la ramificación correcta."
    )
    
    if not en_revision:
        st.success("¡Excelente! No hay carpetas pendientes de revisión.")
    else:
        for reparto in en_revision:
            render_reparto_row(reparto, force_rerun, active_caja=active_caja)

with tab_search:
    st.markdown("### 🔍 Buscador de Repartos")
    st.markdown("Busca cualquier reparto por código (ej: `BB_138232`), sucursal, empresa o número de reparto.")
    
    search_query = st.text_input("Ingrese término de búsqueda:", value="", placeholder="Ej. BB_138232, NQN, 138232...")
    
    if search_query.strip():
        term = search_query.strip().upper()
        results = []
        for r in all_repartos:
            suc = (r["sucursal"] or "").upper()
            num = (r["nro_reparto"] or "").upper()
            emp = (r["empresa"] or "").upper()
            full_code = f"{suc}_{num}"
            
            if (term in full_code or 
                term in num or 
                term in suc or 
                term in emp):
                results.append(r)
                
        if not results:
            st.warning("No se encontraron repartos que coincidan con la búsqueda.")
        else:
            st.markdown(f"**Resultados encontrados: {len(results)}**")
            for r in results:
                estado_badge = "badge-organized" if r["estado"] == "ORGANIZADO" else "badge-revision"
                estado_text = "ORGANIZADO" if r["estado"] == "ORGANIZADO" else "EN REVISIÓN"
                
                with st.container(border=True):
                    col_det, col_btn = st.columns([4, 1])
                    with col_det:
                        st.markdown(
                            f"**Reparto:** `{r['sucursal'] or '?'}_{r['nro_reparto'] or '?'}` &nbsp;&nbsp; "
                            f"<span class='premium-badge {estado_badge}'>{estado_text}</span>", 
                            unsafe_allow_html=True
                        )
                        st.markdown(f"**Empresa:** {r['empresa']} | **Fecha:** {r['fecha'] or 'N/A'}")
                        st.markdown(f"**Ruta:** `{r['ruta_nueva']}`")
                    with col_btn:
                        st.write("")
                        if st.button("📂 Abrir Carpeta", key=f"open_btn_{r['id']}", use_container_width=True):
                            try:
                                res_open = requests.post(f"{API_URL}/api/repartos/{r['id']}/open")
                                if res_open.status_code == 200:
                                    st.toast("Carpeta abierta en el Explorador.")
                                else:
                                    st.error(res_open.json().get("detail", "Error al abrir."))
                            except Exception as ex:
                                st.error(f"Error de conexión: {ex}")

with tab_organizados:
    st.markdown("### 🗂️ Historial de Archivos Organizados")
    st.markdown("Lista de todas las carpetas procesadas y movidas a su estructura jerárquica correspondiente.")
    
    if not organizados:
        st.info("Aún no se han organizado carpetas. Agrega carpetas en `Entrada` y haz clic en **Procesar Entrada**.")
    else:
        # Build pandas DataFrame for display
        df_data = []
        for r in organizados:
            # Shorten paths for better visualization
            ruta_ori = Path(r["ruta_original"]).name
            ruta_nue = r["ruta_nueva"].replace(str(settings.BASE_DIR), "")
            
            df_data.append({
                "ID": r["id"],
                "Empresa": r["empresa"],
                "Fecha": r["fecha"],
                "Sucursal": r["sucursal"],
                "Nro Reparto": r["nro_reparto"],
                "Caja": r.get("caja_codigo") or "S/C",
                "Carpeta Original": ruta_ori,
                "Ruta Destino": ruta_nue
            })
            
        df = pd.DataFrame(df_data)
        
        selection_event = st.dataframe(
            df, 
            use_container_width=True, 
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "ID": st.column_config.NumberColumn(width="small"),
                "Empresa": st.column_config.TextColumn(width="medium"),
                "Fecha": st.column_config.TextColumn(width="medium"),
                "Sucursal": st.column_config.TextColumn(width="small"),
                "Nro Reparto": st.column_config.TextColumn(width="medium"),
                "Caja": st.column_config.TextColumn(width="small"),
                "Carpeta Original": st.column_config.TextColumn(width="medium"),
                "Ruta Destino": st.column_config.TextColumn(width="large"),
            }
        )
        
        # Check if a row is selected
        selected_rows = []
        if selection_event and hasattr(selection_event, "selection"):
            sel = selection_event.selection
            if isinstance(sel, dict):
                selected_rows = sel.get("rows", [])
            else:
                selected_rows = getattr(sel, "rows", [])
        elif isinstance(selection_event, dict) and "selection" in selection_event:
            selected_rows = selection_event["selection"].get("rows", [])
            
        if selected_rows:
            selected_idx = selected_rows[0]
            # Safely fetch the ID to handle sorting or any reindexing issues
            selected_id = df.iloc[selected_idx]["ID"]
            reparto_sel = next((r for r in organizados if r["id"] == selected_id), None)
            
            if reparto_sel:
                st.markdown("---")
                # Sleek container for the selected reparto
                with st.container(border=True):
                    col_info, col_action = st.columns([3, 1])
                    with col_info:
                        st.markdown(
                            f"📁 **Reparto Seleccionado:** `{reparto_sel['sucursal'] or '?'}_{reparto_sel['nro_reparto'] or '?'}` &nbsp;&nbsp;|&nbsp;&nbsp; "
                            f"**Empresa:** {reparto_sel['empresa']} &nbsp;&nbsp;|&nbsp;&nbsp; "
                            f"**Caja:** {reparto_sel.get('caja_codigo') or 'S/C'}"
                        )
                        st.markdown(f"**Ruta Destino Completa:** `{reparto_sel['ruta_nueva']}`")
                    with col_action:
                        st.write("")  # Vertical alignment
                        if st.button("📂 Abrir Carpeta", key="btn_open_organized", use_container_width=True):
                            try:
                                res_open = requests.post(f"{API_URL}/api/repartos/{reparto_sel['id']}/open")
                                if res_open.status_code == 200:
                                    st.toast("Carpeta abierta en el Explorador de Archivos.")
                                else:
                                    st.error(res_open.json().get("detail", "Error al abrir la carpeta."))
                            except Exception as ex:
                                st.error(f"Error de conexión: {ex}")

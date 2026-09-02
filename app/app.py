import streamlit as st
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
import sys
import subprocess

# Add project root to sys.path to enable config imports
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from config.settings import settings, get_persisted_paths, save_persisted_paths

def select_directory_dialog(initial_dir: str) -> str:
    """Opens a native directory selector dialog in a separate subprocess to ensure thread safety."""
    cmd = [
        sys.executable, "-c",
        f"import tkinter as tk; from tkinter import filedialog; root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True); print(filedialog.askdirectory(initialdir={repr(initial_dir)}))"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return res.stdout.strip()
    except Exception:
        return ""

def format_date_display(fecha_str: str) -> str:
    """Formats a YYYY-MM-DD ISO date string to DD/MM/YYYY format for UI presentation."""
    if not fecha_str:
        return "N/A"
    try:
        return datetime.strptime(fecha_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return fecha_str
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

# ----------------- LOGIN SCREEN -----------------
if "user" not in st.session_state or st.session_state["user"] is None:
    st.markdown("<br>", unsafe_allow_html=True)
    _, col_center, _ = st.columns([1, 2, 1])
    with col_center:
        with st.container(border=True):
            st.markdown("### 🔐 Acceso al Sistema")
            st.markdown("Ingrese su **Número de Usuario / Legajo** y **Contraseña / DNI** para operar su puesto de digitalización.")
            
            with st.form("login_form", clear_on_submit=False):
                legajo_input = st.text_input("👤 Número de Usuario / Legajo:", placeholder="Ej. 1101")
                password_input = st.text_input("🔑 Contraseña (DNI):", type="password", placeholder="••••••••")
                btn_login = st.form_submit_button("🚀 Iniciar Sesión", use_container_width=True)
                
                if btn_login:
                    if not legajo_input.strip() or not password_input.strip():
                        st.error("Por favor completa todos los campos.")
                    else:
                        try:
                            res_login = requests.post(
                                f"{API_URL}/api/auth/login",
                                json={"legajo": legajo_input.strip(), "password": password_input.strip()}
                            )
                            if res_login.status_code == 200:
                                st.session_state["user"] = res_login.json()["user"]
                                st.rerun()
                            else:
                                st.error(res_login.json().get("detail", "Credenciales incorrectas."))
                        except Exception as ex:
                            st.error(f"Error al conectar con el servidor: {ex}")
    st.stop()

# ----------------- LOGGED IN USER CONTEXT -----------------
current_user = st.session_state["user"]

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
                res_close = requests.post(
                    f"{API_URL}/api/cajas/active/close",
                    json={"usuario_id": current_user["id"]}
                )
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
        
    res_caja = requests.get(f"{API_URL}/api/cajas/active?usuario_id={current_user['id']}")
    if res_caja.status_code == 200:
        active_caja = res_caja.json()
except Exception as e:
    st.warning("El servidor backend no está respondiendo. Por favor, asegúrate de que el backend esté iniciado.")
    st.info("Puedes iniciar el servidor backend ejecutando el archivo `launcher.py` en tu terminal.")

# Sidebar user card & controls
st.sidebar.markdown(f"### 👤 Operador: `{current_user['legajo']}`")
st.sidebar.markdown(f"**Nombre:** {current_user['nombre']} &nbsp;|&nbsp; **Rol:** `{current_user['rol']}`")

col_logout, col_pwd = st.sidebar.columns([1, 1])
with col_logout:
    if st.button("🚪 Salir", use_container_width=True):
        st.session_state["user"] = None
        st.rerun()
with col_pwd:
    with st.popover("🔑 Clave"):
        st.markdown("##### Cambiar mi contraseña")
        p_act = st.text_input("Clave Actual:", type="password", key="p_act_input")
        p_new = st.text_input("Nueva Clave / DNI:", type="password", key="p_new_input")
        if st.button("Guardar Nueva Clave", key="btn_save_my_pwd", use_container_width=True):
            if not p_act.strip() or not p_new.strip():
                st.error("Completa ambos campos.")
            else:
                try:
                    r_chg = requests.post(
                        f"{API_URL}/api/auth/users/{current_user['id']}/change-password",
                        json={"password_actual": p_act.strip(), "password_nueva": p_new.strip()}
                    )
                    if r_chg.status_code == 200:
                        st.toast("Contraseña actualizada con éxito.")
                    else:
                        st.error(r_chg.json().get("detail", "Error al cambiar contraseña."))
                except Exception as ex:
                    st.error(f"Error: {ex}")

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Panel de Operaciones")
st.sidebar.info(
    "Este sistema escanea la carpeta especificada para digitalizar y organizar automáticamente "
    "las carpetas según su **Hoja de Reparto**."
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📂 Selección de Carpeta")

# Load persistent directory paths from user_config.json
persisted_paths = get_persisted_paths()

if "scan_path_input" not in st.session_state:
    st.session_state["scan_path_input"] = persisted_paths.get("scan_path", str(Path(settings.ENTRADA).resolve()))

if "salida_path_input" not in st.session_state:
    st.session_state["salida_path_input"] = persisted_paths.get("salida_path", str(Path(settings.SALIDA).resolve()))

# Apply picker updates BEFORE widgets are instantiated to avoid StreamlitAPIException
if "selected_scan_path" in st.session_state:
    new_scan = st.session_state.pop("selected_scan_path")
    st.session_state["scan_path_input"] = new_scan
    save_persisted_paths(scan_path=new_scan)

if "selected_salida_path" in st.session_state:
    new_salida = st.session_state.pop("selected_salida_path")
    st.session_state["salida_path_input"] = new_salida
    save_persisted_paths(salida_path=new_salida)

def on_scan_path_change():
    save_persisted_paths(scan_path=st.session_state.get("scan_path_input"))

def on_salida_path_change():
    save_persisted_paths(salida_path=st.session_state.get("salida_path_input"))

# Folder to scan: Text input + picker button
col_scan_text, col_scan_btn = st.sidebar.columns([4, 1])
with col_scan_text:
    scan_path = st.text_input(
        "Carpeta a escanear:",
        help="Ruta absoluta de la carpeta a procesar. Se recordará en todas las sesiones.",
        key="scan_path_input",
        on_change=on_scan_path_change
    )

with col_scan_btn:
    st.write("") # vertical alignment spacing
    st.write("")
    if st.button("📁", key="btn_pick_scan", help="Seleccionar carpeta de entrada..."):
        selected = select_directory_dialog(st.session_state["scan_path_input"])
        if selected:
            st.session_state["selected_scan_path"] = str(Path(selected).resolve())
            st.rerun()

# Output folder: Text input + picker button
col_sal_text, col_sal_btn = st.sidebar.columns([4, 1])
with col_sal_text:
    salida_path = st.text_input(
        "Carpeta de Salida:",
        help="Ruta absoluta de la carpeta donde se moverán los archivos organizados. Se recordará en todas las sesiones.",
        key="salida_path_input",
        on_change=on_salida_path_change
    )

with col_sal_btn:
    st.write("") # vertical alignment spacing
    st.write("")
    if st.button("📁", key="btn_pick_salida", help="Seleccionar carpeta de salida..."):
        selected = select_directory_dialog(st.session_state["salida_path_input"])
        if selected:
            st.session_state["selected_salida_path"] = str(Path(selected).resolve())
            st.rerun()

st.sidebar.markdown(f"**Revisión:** `{settings.REVISION}`")
st.sidebar.markdown("---")

# Select processing mode
modo_seleccionado = st.sidebar.radio(
    "Modo de Digitalización:",
    options=[
        "Operación Estándar (Control Completo)",
        "Histórico Anterior (Virtual)"
    ],
    index=0,
    help=(
        "**Operación Estándar:** Requiere tener una caja física activa, valida metadatos oficiales y exige control de guías faltantes y firmas.\n\n"
        "**Histórico Anterior:** No requiere caja física (asigna a CAJA-HISTORICA-DIGITAL) y digitaliza sin frenar por faltantes o firmas."
    )
)

modo_historico = (modo_seleccionado == "Histórico Anterior (Virtual)")

# Action button to trigger processing
if st.sidebar.button("🚀 Procesar Entrada", type="primary", use_container_width=True):
    if not scan_path:
        st.sidebar.error("Por favor especifique la ruta de la carpeta a escanear.")
    else:
        with st.spinner("Procesando archivos PDF en la carpeta de entrada..."):
            try:
                payload = {
                    "path": scan_path.strip(),
                    "salida_path": salida_path.strip() if salida_path else None,
                    "modo_historico": modo_historico,
                    "usuario_id": current_user["id"],
                    "usuario_legajo": current_user["legajo"]
                }
                res = requests.post(f"{API_URL}/api/process", json=payload)
                if res.status_code == 200:
                    data = res.json().get("data", {})
                    organizados = data.get("organizados", [])
                    revision = data.get("revision", [])
                    
                    if organizados or revision:
                        st.toast(f"Procesados: {len(organizados)} organizados, {len(revision)} a revisión.")
                    else:
                        st.toast("No se encontraron carpetas nuevas con PDFs.")
                else:
                    st.sidebar.error(f"Error: {res.json().get('detail', 'Error desconocido')}")
            except Exception as e:
                st.sidebar.error(f"No se pudo conectar al servidor backend: {e}")

st.sidebar.markdown("---")
st.sidebar.markdown("### 📦 Mi Caja de Archivo Físico")

if active_caja:
    st.sidebar.success(f"**Caja Activa Asignada:** `{active_caja['codigo']}`")
    if st.sidebar.button("🔒 Cerrar Mi Caja Activa", use_container_width=True):
        close_caja_dialog(active_caja['codigo'])
else:
    st.sidebar.info("No tienes una caja activa abierta. Abre una caja para comenzar a digitalizar.")
    if st.sidebar.button("➕ Abrir Mi Siguiente Caja", use_container_width=True):
        try:
            res_new = requests.post(
                f"{API_URL}/api/cajas/new", 
                json={"usuario_id": current_user["id"], "usuario_legajo": current_user["legajo"]}
            )
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
is_admin = (current_user.get("rol") == "ADMIN")

if is_admin:
    tab_revision, tab_search, tab_organizados, tab_operadores = st.tabs([
        f"⚠️ En Revisión ({len(en_revision)})", 
        "🔍 Buscar Reparto",
        f"✓ Organizados ({len(organizados)})",
        "👥 Gestión de Operadores"
    ])
else:
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
        # Pagination settings
        ITEMS_PER_PAGE = 10
        total_items = len(en_revision)
        import math
        total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
        
        # Initialize page state
        if "revision_page" not in st.session_state:
            st.session_state["revision_page"] = 1
            
        # Limit page bounds
        if st.session_state["revision_page"] > total_pages:
            st.session_state["revision_page"] = max(1, total_pages)
            
        current_page = st.session_state["revision_page"]
        
        # Render top pagination controls
        col_prev, col_page, col_next = st.columns([1, 2, 1])
        with col_prev:
            if st.button("⬅️ Anterior", disabled=(current_page == 1), key="page_prev_top", use_container_width=True):
                st.session_state["revision_page"] = current_page - 1
                st.rerun()
        with col_page:
            st.markdown(
                f"<div style='text-align: center; font-weight: bold;'>Página {current_page} de {total_pages}</div>"
                f"<div style='text-align: center; color: #888; font-size: 0.85rem;'>Mostrando {((current_page-1)*ITEMS_PER_PAGE)+1}-{min(total_items, current_page*ITEMS_PER_PAGE)} de {total_items} casos</div>",
                unsafe_allow_html=True
            )
        with col_next:
            if st.button("Siguiente ➡️", disabled=(current_page == total_pages), key="page_next_top", use_container_width=True):
                st.session_state["revision_page"] = current_page + 1
                st.rerun()
                
        st.markdown("---")
        
        # Get paginated slice
        start_idx = (current_page - 1) * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        paginated_revision = en_revision[start_idx:end_idx]
        
        for reparto in paginated_revision:
            render_reparto_row(
                reparto, 
                force_rerun, 
                active_caja=active_caja, 
                salida_path=salida_path,
                modo_historico=modo_historico,
                current_user=current_user
            )
            
        st.markdown("---")
        
        # Render bottom pagination controls
        col_prev_b, col_page_b, col_next_b = st.columns([1, 2, 1])
        with col_prev_b:
            if st.button("⬅️ Anterior", disabled=(current_page == 1), key="page_prev_bottom", use_container_width=True):
                st.session_state["revision_page"] = current_page - 1
                st.rerun()
        with col_page_b:
            st.markdown(
                f"<div style='text-align: center; font-weight: bold;'>Página {current_page} de {total_pages}</div>",
                unsafe_allow_html=True
            )
        with col_next_b:
            if st.button("Siguiente ➡️", disabled=(current_page == total_pages), key="page_next_bottom", use_container_width=True):
                st.session_state["revision_page"] = current_page + 1
                st.rerun()

with tab_search:
    st.markdown("### 🔍 Buscador Inteligente (Repartos y Guías Individuales)")
    st.markdown("Busca por **Número de Reparto** (ej: `138232`), **Sucursal** (`BB`, `NQN`), **Operador** (`1101`) o **Número de Guía Individual** (ej: `845563` o `BB.1.845563`).")
    
    search_query = st.text_input("Ingrese término de búsqueda:", value="", placeholder="Ej. 138232, 845563, BB.1.845563, NQN, 1101...")
    
    if search_query.strip():
        term = search_query.strip().upper()
        results = []
        for r in all_repartos:
            suc = (r["sucursal"] or "").upper()
            num = (r["nro_reparto"] or "").upper()
            emp = (r["empresa"] or "").upper()
            op = (r.get("usuario_legajo") or "").upper()
            enc = (r.get("guias_encontradas") or "").upper()
            fal = (r.get("guias_faltantes") or "").upper()
            noe = (r.get("guias_no_entregadas") or "").upper()
            full_code = f"{suc}_{num}"
            
            # Check match in any field
            matched_guia_info = None
            if term in enc:
                matched_guia_info = {"status": "DIGITALIZADA", "color": "#16a34a", "icon": "✅", "desc": "Digitalizada y presente en archivo"}
            elif term in fal:
                matched_guia_info = {"status": "FALTANTE", "color": "#dc2626", "icon": "⚠️", "desc": "Guía Faltante (no se encontró PDF al momento del escaneo)"}
            elif term in noe:
                matched_guia_info = {"status": "NO_ENTREGADA", "color": "#2563eb", "icon": "🚫", "desc": "Marcada como 'NO' entregada en Hoja de Reparto"}
                
            if (term in full_code or 
                term in num or 
                term in suc or 
                term in emp or
                term in op or
                matched_guia_info is not None):
                results.append((r, matched_guia_info))
                
        if not results:
            st.warning("No se encontraron repartos ni guías que coincidan con la búsqueda.")
        else:
            st.markdown(f"**Resultados encontrados: {len(results)}**")
            for r, matched_guia_info in results:
                estado_badge = "badge-organized" if r["estado"] == "ORGANIZADO" else "badge-revision"
                estado_text = "ORGANIZADO" if r["estado"] == "ORGANIZADO" else "EN REVISIÓN"
                
                with st.container(border=True):
                    # If this was a match for an individual guía, display direct guia banner
                    if matched_guia_info:
                        st.markdown(
                            f"<div style='background-color: {matched_guia_info['color']}15; border-left: 4px solid {matched_guia_info['color']}; padding: 8px 12px; border-radius: 4px; margin-bottom: 10px;'>"
                            f"<strong>{matched_guia_info['icon']} Coincidencia de Guía Individual:</strong> <code>{term}</code> &nbsp;|&nbsp; "
                            f"<strong>Estado:</strong> {matched_guia_info['desc']} &nbsp;|&nbsp; "
                            f"📦 <strong>Caja Física:</strong> <code>{r.get('caja_codigo') or 'S/C'}</code>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                        
                    col_det, col_btn = st.columns([3, 1])
                    with col_det:
                        dup_badge = "<span style='background-color: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; margin-left: 6px;'>DUPLICADO</span>" if r.get("es_duplicado") else ""
                        st.markdown(
                            f"**Reparto:** `{r['sucursal'] or '?'}_{r['nro_reparto'] or '?'}` &nbsp;&nbsp; "
                            f"<span class='premium-badge {estado_badge}'>{estado_text}</span>{dup_badge}", 
                            unsafe_allow_html=True
                        )
                        st.markdown(
                            f"**Empresa:** {r['empresa']} | **Fecha:** {format_date_display(r['fecha'])} | "
                            f"📦 **Caja:** `{r.get('caja_codigo') or 'S/C'}` | "
                            f"👤 **Operador:** `{r.get('usuario_legajo') or 'S/A'}`"
                        )
                        if r.get("guias_faltantes"):
                            st.markdown(f"⚠️ **Guías Faltantes:** `{r['guias_faltantes'].replace(',', ', ')}`")
                        if r.get("guias_sin_firma"):
                            st.markdown(f"✍️ **Guías Sin Firma:** `{r['guias_sin_firma'].replace(',', ', ')}`")
                        if r.get("guias_no_entregadas"):
                            st.markdown(f"🚫 **Guías No Entregadas:** `{r['guias_no_entregadas'].replace(',', ', ')}`")
                        st.markdown(f"**Ruta:** `{r['ruta_nueva'] or r['ruta_original']}`")
                        
                    with col_btn:
                        st.write("")
                        if st.button("📂 Explorador Local", key=f"open_btn_{r['id']}", use_container_width=True):
                            try:
                                res_open = requests.post(f"{API_URL}/api/repartos/{r['id']}/open")
                                if res_open.status_code == 200:
                                    st.toast("Carpeta abierta en el Explorador.")
                                else:
                                    st.error(res_open.json().get("detail", "Error al abrir."))
                            except Exception as ex:
                                st.error(f"Error de conexión: {ex}")
                                
                    # Fetch and display web PDF files directly
                    with st.expander("📄 Ver / Descargar Documentos PDF de este Reparto"):
                        try:
                            r_files = requests.get(f"{API_URL}/api/repartos/{r['id']}/files")
                            if r_files.status_code == 200:
                                pdf_list = r_files.json()
                                if not pdf_list:
                                    st.info("No se encontraron archivos PDF en la carpeta de este reparto.")
                                else:
                                    for pdf_f in pdf_list:
                                        file_url = f"{API_URL}/api/repartos/{r['id']}/files/{pdf_f['name']}"
                                        c_f1, c_f2 = st.columns([3, 1])
                                        with c_f1:
                                            icon_p = "📋" if pdf_f.get("is_hoja") else "📄"
                                            st.markdown(f"{icon_p} **{pdf_f['name']}** <span style='color: #888; font-size: 0.8rem;'>({pdf_f['size_kb']} KB)</span>", unsafe_allow_html=True)
                                        with c_f2:
                                            st.markdown(
                                                f"<a href='{file_url}' target='_blank' style='display: inline-block; width: 100%; text-align: center; background-color: #2563eb; color: white; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 0.85rem; font-weight: bold;'>👁️ Ver PDF</a>",
                                                unsafe_allow_html=True
                                            )
                            else:
                                st.error("No se pudo cargar la lista de archivos.")
                        except Exception as e_f:
                            st.error(f"Error al listar PDFs: {e_f}")

with tab_organizados:
    st.markdown("### 🗂️ Historial de Archivos Organizados")
    st.markdown("Lista de todas las carpetas procesadas y movidas a su estructura jerárquica correspondiente.")
    
    if not organizados:
        st.info("Aún no se han organizado carpetas. Agrega carpetas en `Entrada` y haz clic en **Procesar Entrada**.")
    else:
        # Build pandas DataFrame for display and export
        df_data = []
        for r in organizados:
            ruta_ori = Path(r["ruta_original"]).name
            ruta_nue = r["ruta_nueva"].replace(str(settings.BASE_DIR), "")
            
            df_data.append({
                "ID": r["id"],
                "Empresa": r["empresa"],
                "Fecha": format_date_display(r["fecha"]),
                "Sucursal": r["sucursal"],
                "Nro Reparto": r["nro_reparto"],
                "Caja": r.get("caja_codigo") or "S/C",
                "Operador": r.get("usuario_legajo") or "S/A",
                "Duplicado": "⚠️ Sí" if r.get("es_duplicado") else "No",
                "Guías Faltantes": (r.get("guias_faltantes") or "").replace(",", ", ") if r.get("guias_faltantes") else "Ninguna",
                "Sin Firma": (r.get("guias_sin_firma") or "").replace(",", ", ") if r.get("guias_sin_firma") else "Ninguna",
                "No Entregadas": (r.get("guias_no_entregadas") or "").replace(",", ", ") if r.get("guias_no_entregadas") else "Ninguna",
                "Fecha Procesamiento": r.get("fecha_procesamiento") or "",
                "Carpeta Original": ruta_ori,
                "Ruta Destino": ruta_nue
            })
            
        df = pd.DataFrame(df_data)

        # Excel Export Section
        col_exp1, col_exp2 = st.columns([3, 1])
        with col_exp1:
            st.markdown(f"**Total de repartos organizados:** `{len(df)}`")
        with col_exp2:
            import io
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name="Repartos")
            
            st.download_button(
                label="📥 Exportar a Excel (.xlsx)",
                data=excel_buffer.getvalue(),
                file_name=f"Reporte_Repartos_{date.today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
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
                "Operador": st.column_config.TextColumn(width="small"),
                "Duplicado": st.column_config.TextColumn(width="small"),
                "Guías Faltantes": st.column_config.TextColumn(width="medium"),
                "Sin Firma": st.column_config.TextColumn(width="medium"),
                "No Entregadas": st.column_config.TextColumn(width="medium"),
                "Fecha Procesamiento": st.column_config.TextColumn(width="medium"),
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
                        dup_badge_sel = " &nbsp;<span style='background-color: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold;'>⚠️ REPARTO DUPLICADO / REIMPRESIÓN</span>" if reparto_sel.get("es_duplicado") else ""
                        st.markdown(
                            f"📁 **Reparto Seleccionado:** `{reparto_sel['sucursal'] or '?'}_{reparto_sel['nro_reparto'] or '?'}`{dup_badge_sel} &nbsp;&nbsp;|&nbsp;&nbsp; "
                            f"**Empresa:** {reparto_sel['empresa']} &nbsp;&nbsp;|&nbsp;&nbsp; "
                            f"**Caja:** {reparto_sel.get('caja_codigo') or 'S/C'} &nbsp;&nbsp;|&nbsp;&nbsp; "
                            f"👤 **Operador:** `{reparto_sel.get('usuario_legajo') or 'S/A'}`",
                            unsafe_allow_html=True
                        )
                        st.markdown(f"**Ruta Destino Completa:** `{reparto_sel['ruta_nueva']}`")
                        if reparto_sel.get("guias_faltantes"):
                            st.markdown(f"⚠️ **Guías Faltantes:** `{reparto_sel['guias_faltantes'].replace(',', ', ')}`")
                        if reparto_sel.get("guias_sin_firma"):
                            st.markdown(f"✍️ **Guías Sin Firma:** `{reparto_sel['guias_sin_firma'].replace(',', ', ')}`")
                        if reparto_sel.get("guias_no_entregadas"):
                            st.markdown(f"🚫 **Guías No Entregadas (Marcadas 'NO' en Hoja):** `{reparto_sel['guias_no_entregadas'].replace(',', ', ')}`")
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

                    # List and view PDF files directly in web
                    st.markdown("##### 📄 Documentos Digitalizados (Acceso Web)")
                    try:
                        r_files = requests.get(f"{API_URL}/api/repartos/{reparto_sel['id']}/files")
                        if r_files.status_code == 200:
                            pdf_list = r_files.json()
                            if not pdf_list:
                                st.info("No se encontraron archivos PDF.")
                            else:
                                for pdf_f in pdf_list:
                                    file_url = f"{API_URL}/api/repartos/{reparto_sel['id']}/files/{pdf_f['name']}"
                                    c_f1, c_f2 = st.columns([3, 1])
                                    with c_f1:
                                        icon_p = "📋" if pdf_f.get("is_hoja") else "📄"
                                        st.markdown(f"{icon_p} **{pdf_f['name']}** <span style='color: #888; font-size: 0.8rem;'>({pdf_f['size_kb']} KB)</span>", unsafe_allow_html=True)
                                    with c_f2:
                                        st.markdown(
                                            f"<a href='{file_url}' target='_blank' style='display: inline-block; width: 100%; text-align: center; background-color: #2563eb; color: white; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 0.85rem; font-weight: bold;'>👁️ Ver PDF</a>",
                                            unsafe_allow_html=True
                                        )
                    except Exception as e_f:
                        st.error(f"Error al listar PDFs: {e_f}")

# ----------------- ADMIN OPERATOR MANAGEMENT TAB -----------------
if is_admin:
    with tab_operadores:
        st.markdown("### 👥 Administración de Operadores de Escáner")
        st.markdown("Administra los usuarios autorizados para operar los puestos de digitalización y monitorea su productividad.")
        
        col_new_user, col_list_users = st.columns([1, 2])
        
        # New Operator Form
        with col_new_user:
            with st.container(border=True):
                st.markdown("##### ➕ Alta de Nuevo Operador")
                with st.form("new_operator_form", clear_on_submit=True):
                    new_legajo = st.text_input("Número de Usuario / Legajo:", placeholder="Ej. 1102")
                    new_nombre = st.text_input("Nombre y Apellido:", placeholder="Ej. Lucas")
                    new_pwd = st.text_input("DNI / Contraseña Inicial:", type="password", placeholder="Ej. 41234567")
                    new_rol = st.selectbox("Rol del Usuario:", options=["OPERADOR", "ADMIN"], index=0)
                    
                    submit_user = st.form_submit_button("Crear Operador", use_container_width=True)
                    if submit_user:
                        if not new_legajo.strip() or not new_nombre.strip() or not new_pwd.strip():
                            st.error("Por favor completa todos los campos del nuevo operador.")
                        else:
                            try:
                                r_create = requests.post(
                                    f"{API_URL}/api/auth/users/create",
                                    json={
                                        "legajo": new_legajo.strip(),
                                        "nombre": new_nombre.strip(),
                                        "password": new_pwd.strip(),
                                        "rol": new_rol
                                    }
                                )
                                if r_create.status_code == 200:
                                    st.success(f"¡Operador {new_legajo} ({new_nombre}) creado con éxito!")
                                    st.rerun()
                                else:
                                    st.error(r_create.json().get("detail", "Error al crear operador."))
                            except Exception as ex:
                                st.error(f"Error de conexión: {ex}")
                                
        # Operator List & Productivity
        with col_list_users:
            st.markdown("##### 📋 Operadores Registrados")
            try:
                r_users = requests.get(f"{API_URL}/api/auth/users")
                if r_users.status_code == 200:
                    users_data = r_users.json()
                    
                    for u in users_data:
                        with st.container(border=True):
                            c_u1, c_u2, c_u3 = st.columns([2, 2, 2])
                            with c_u1:
                                estado_icon = "🟢 Activo" if u["activo"] else "🔴 Inactivo"
                                st.markdown(f"**Legajo `{u['legajo']}`** ({u['nombre']})")
                                st.markdown(f"Rol: `{u['rol']}` &nbsp;|&nbsp; {estado_icon}")
                            with c_u2:
                                st.markdown(f"📁 Repartos: **{u.get('total_repartos', 0)}**")
                                st.markdown(f"📦 Cajas: **{u.get('total_cajas', 0)}**")
                            with c_u3:
                                with st.popover("⚙️ Acciones"):
                                    st.markdown(f"**Opciones para {u['legajo']}**")
                                    # Toggle active
                                    toggle_label = "Desactivar Usuario" if u["activo"] else "Activar Usuario"
                                    if st.button(toggle_label, key=f"tgl_{u['id']}", use_container_width=True):
                                        requests.post(f"{API_URL}/api/auth/users/{u['id']}/toggle")
                                        st.rerun()
                                    
                                    # Reset password / DNI
                                    st.markdown("---")
                                    st.markdown("##### Restablecer Clave (DNI)")
                                    reset_pwd_input = st.text_input("Nueva Clave / DNI:", type="password", key=f"rst_p_{u['id']}")
                                    if st.button("Guardar Clave", key=f"btn_rst_{u['id']}", use_container_width=True):
                                        if reset_pwd_input.strip():
                                            r_rst = requests.post(
                                                f"{API_URL}/api/auth/users/{u['id']}/reset-password",
                                                json={"password_nueva": reset_pwd_input.strip()}
                                            )
                                            if r_rst.status_code == 200:
                                                st.toast(f"Clave restablecida para {u['legajo']}.")
                                                st.rerun()
                                            else:
                                                st.error("Error al restablecer.")
                else:
                    st.error("Error al obtener la lista de operadores.")
            except Exception as ex:
                st.error(f"Error al conectar con la API: {ex}")

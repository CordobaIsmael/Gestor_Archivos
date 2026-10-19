import streamlit as st
import streamlit.components.v1 as components
import requests
import base64
from datetime import date, datetime
from pathlib import Path
import fitz  # PyMuPDF
from config.settings import settings, validate_nro_reparto_digits, get_min_digits_for_sucursal
from services.file_manager import get_network_unc_path

API_URL = settings.API_URL

def render_interactive_pdf_viewer(b64_img: str, height: int = 580):
    """Renders a responsive, interactive pan & zoom PDF image viewer with zero external dependencies."""
    html_code = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: #0f172a;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    user-select: none;
    -webkit-user-select: none;
  }}
  #viewer-container {{
    position: relative;
    width: 100%;
    height: {height}px;
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    overflow: hidden;
  }}
  #controls {{
    position: absolute;
    top: 10px;
    right: 10px;
    z-index: 50;
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(15, 23, 42, 0.9);
    padding: 4px 8px;
    border-radius: 6px;
    border: 1px solid #475569;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
  }}
  .btn-zoom {{
    background: #334155;
    color: #f8fafc;
    border: 1px solid #475569;
    border-radius: 4px;
    width: 28px;
    height: 28px;
    font-size: 14px;
    font-weight: bold;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    outline: none;
    transition: background 0.15s, transform 0.1s;
  }}
  .btn-zoom:hover {{
    background: #475569;
    color: #38bdf8;
  }}
  .btn-zoom:active {{
    transform: scale(0.92);
  }}
  #zoom-label {{
    color: #94a3b8;
    font-size: 12px;
    font-weight: 600;
    padding: 0 6px;
    min-width: 48px;
    text-align: center;
  }}
  #hint {{
    position: absolute;
    bottom: 8px;
    left: 10px;
    z-index: 40;
    color: #94a3b8;
    font-size: 11px;
    background: rgba(15, 23, 42, 0.85);
    padding: 3px 8px;
    border-radius: 4px;
    pointer-events: none;
    border: 1px solid rgba(71, 85, 105, 0.5);
  }}
  #viewport {{
    width: 100%;
    height: 100%;
    position: relative;
    overflow: hidden;
    cursor: grab;
  }}
  #viewport:active {{
    cursor: grabbing;
  }}
  #content-wrapper {{
    position: absolute;
    top: 0;
    left: 0;
    transform-origin: 0 0;
    will-change: transform;
  }}
  #pdf-img {{
    display: block;
    box-shadow: 0 4px 25px rgba(0,0,0,0.7);
    border-radius: 2px;
  }}
</style>
</head>
<body>
  <div id="viewer-container">
    <div id="controls">
      <button class="btn-zoom" id="btn-in" title="Acercar (Rueda arriba)">➕</button>
      <button class="btn-zoom" id="btn-out" title="Alejar (Rueda abajo)">➖</button>
      <div id="zoom-label">100%</div>
      <button class="btn-zoom" id="btn-reset" title="Restablecer tamaño">↺</button>
    </div>
    <div id="hint">🔍 Rueda: Zoom • Clic: Arrastrar • Doble clic: Alternar aumento</div>
    <div id="viewport">
      <div id="content-wrapper">
        <img id="pdf-img" src="data:image/png;base64,{b64_img}" draggable="false" />
      </div>
    </div>
  </div>

  <script>
    const viewport = document.getElementById('viewport');
    const wrapper = document.getElementById('content-wrapper');
    const img = document.getElementById('pdf-img');
    const zoomLabel = document.getElementById('zoom-label');
    const btnIn = document.getElementById('btn-in');
    const btnOut = document.getElementById('btn-out');
    const btnReset = document.getElementById('btn-reset');

    let initialScale = 1.0;
    let currentScale = 1.0;
    let posX = 0;
    let posY = 0;
    let isDragging = false;
    let startX = 0;
    let startY = 0;

    function applyTransform() {{
      wrapper.style.transform = `translate(${{posX}}px, ${{posY}}px) scale(${{currentScale}})`;
      const pct = Math.round((currentScale / initialScale) * 100);
      zoomLabel.textContent = `${{pct}}%`;
    }}

    function initView() {{
      const vw = viewport.clientWidth || 500;
      const vh = viewport.clientHeight || {height};
      const nw = img.naturalWidth || 800;
      const nh = img.naturalHeight || 1100;

      // Fit page to width with 12px margin
      initialScale = Math.min((vw - 24) / nw, 1.0);
      currentScale = initialScale;
      posX = Math.max(12, (vw - nw * currentScale) / 2);
      posY = 10;
      applyTransform();
    }}

    img.onload = initView;
    if (img.complete) initView();

    // Pan / Dragging
    viewport.addEventListener('mousedown', (e) => {{
      if (e.button !== 0) return;
      isDragging = true;
      startX = e.clientX - posX;
      startY = e.clientY - posY;
      viewport.style.cursor = 'grabbing';
    }});

    window.addEventListener('mousemove', (e) => {{
      if (!isDragging) return;
      posX = e.clientX - startX;
      posY = e.clientY - startY;
      applyTransform();
    }});

    window.addEventListener('mouseup', () => {{
      if (isDragging) {{
        isDragging = false;
        viewport.style.cursor = 'grab';
      }}
    }});

    // Wheel Zoom centered on mouse pointer
    viewport.addEventListener('wheel', (e) => {{
      e.preventDefault();
      const delta = e.deltaY < 0 ? 1.15 : 0.87;
      zoomAtPoint(e.clientX, e.clientY, delta);
    }}, {{ passive: false }});

    function zoomAtPoint(clientX, clientY, factor) {{
      const rect = viewport.getBoundingClientRect();
      const mouseX = clientX - rect.left;
      const mouseY = clientY - rect.top;

      const contentX = (mouseX - posX) / currentScale;
      const contentY = (mouseY - posY) / currentScale;

      let newScale = currentScale * factor;
      const minScale = initialScale * 0.5;
      const maxScale = initialScale * 6.0;

      if (newScale < minScale) newScale = minScale;
      if (newScale > maxScale) newScale = maxScale;

      posX = mouseX - contentX * newScale;
      posY = mouseY - contentY * newScale;
      currentScale = newScale;
      applyTransform();
    }}

    // Zoom Buttons
    btnIn.addEventListener('click', () => {{
      const rect = viewport.getBoundingClientRect();
      zoomAtPoint(rect.left + rect.width / 2, rect.top + rect.height / 2, 1.25);
    }});

    btnOut.addEventListener('click', () => {{
      const rect = viewport.getBoundingClientRect();
      zoomAtPoint(rect.left + rect.width / 2, rect.top + rect.height / 2, 0.8);
    }});

    btnReset.addEventListener('click', initView);

    // Double click to toggle between 2x and overview
    viewport.addEventListener('dblclick', (e) => {{
      if (currentScale > initialScale * 1.5) {{
        initView();
      }} else {{
        zoomAtPoint(e.clientX, e.clientY, 2.0);
      }}
    }});
  </script>
</body>
</html>"""
    components.html(html_code, height=height + 10)

def inject_custom_css():
    """Injects high-quality premium CSS to override default Streamlit styles."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Outfit', sans-serif;
        }
        
        /* Main background and card styling */
        .main-header {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #6366f1, #a855f7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }
        
        .sub-header {
            font-size: 1.1rem;
            color: #94a3b8;
            margin-bottom: 2rem;
        }
        
        /* Metric Cards */
        .card-container {
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
        }
        
        .stat-card {
            flex: 1;
            background: rgba(30, 41, 59, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 1.5rem;
            text-align: center;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            transition: transform 0.3s ease, border-color 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            border-color: rgba(99, 102, 241, 0.4);
        }
        
        .stat-card.organized {
            border-left: 4px solid #10b981;
        }
        
        .stat-card.revision {
            border-left: 4px solid #f59e0b;
        }

        .stat-card.primary {
            border-left: 4px solid #3b82f6;
        }

        .stat-card.info {
            border-left: 4px solid #06b6d4;
        }

        .stat-card.purple {
            border-left: 4px solid #a855f7;
        }

        
        .stat-value {
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 0.2rem;
        }
        
        .stat-label {
            font-size: 0.9rem;
            font-weight: 600;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        /* Interactive tables */
        .premium-table {
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
            font-size: 0.95rem;
            background: #1e293b;
            border-radius: 12px;
            overflow: hidden;
        }
        
        .premium-table th {
            background-color: #334155;
            color: #f8fafc;
            text-align: left;
            padding: 12px 16px;
            font-weight: 600;
        }
        
        .premium-table td {
            padding: 12px 16px;
            border-bottom: 1px solid #334155;
            color: #cbd5e1;
        }
        
        .premium-table tr:last-child td {
            border-bottom: none;
        }
        
        .premium-badge {
            display: inline-block;
            padding: 4px 8px;
            font-size: 0.75rem;
            font-weight: 700;
            border-radius: 9999px;
            text-transform: uppercase;
        }
        
        .badge-organized {
            background: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }
        
        .badge-revision {
            background: rgba(245, 158, 11, 0.15);
            color: #f59e0b;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }
        
        .badge-anulado {
            background: rgba(239, 68, 68, 0.15);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }
        
        /* Buttons custom overrides */
        div.stButton > button:first-child {
            background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
            color: white;
            border: none;
            padding: 0.6rem 1.8rem;
            font-weight: 600;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
            transition: all 0.3s ease;
        }
        
        div.stButton > button:first-child:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(99, 102, 241, 0.5);
            background: linear-gradient(135deg, #4f46e5 0%, #9333ea 100%);
        }
        </style>
        """,
        unsafe_allow_html=True
    )

def render_header():
    """Renders the top branding of the application."""
    st.markdown('<div class="main-header">GestorArchivo</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Digitalización y Organización Inteligente de Repartos</div>', unsafe_allow_html=True)

def render_stats(organized_count: int, revision_count: int):
    """Renders sleek glassmorphic stats cards."""
    st.markdown(
        f"""
        <div class="card-container">
            <div class="stat-card organized">
                <div class="stat-value" style="color: #10b981;">{organized_count}</div>
                <div class="stat-label">Organizados con Éxito</div>
            </div>
            <div class="stat-card revision">
                <div class="stat-value" style="color: #f59e0b;">{revision_count}</div>
                <div class="stat-label">Requieren Revisión</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_reparto_row(reparto: dict, on_resolve_callback, salida_path=None, modo_historico=False, current_user=None):
    """Renders an interactive manual editor and PDF viewer inside a collapsible container for Revision items."""
    folder_path = Path(reparto['ruta_nueva'])
    folder_name = folder_path.name
    
    # Keep expander open if user has interacted with any field or selected a PDF in this reparto
    is_active = (
        f"pdf_sel_{reparto['id']}" in st.session_state or 
        f"pdf_page_{reparto['id']}" in st.session_state or
        f"suc_{reparto['id']}" in st.session_state or
        f"num_{reparto['id']}" in st.session_state or
        f"emp_{reparto['id']}" in st.session_state
    )
    
    is_admin = bool(current_user and current_user.get("rol") == "ADMIN")
    es_devuelto = bool(reparto.get("motivo_revision") and "Devuelto" in str(reparto.get("motivo_revision")))
    is_blocked_for_operator = bool(es_devuelto and not is_admin)

    badge_rev = " 🔄 [DEVUELTO A REVISIÓN]" if es_devuelto else ""
    with st.expander(f"📁 {folder_name}{badge_rev} (ID: {reparto['id']})", expanded=is_active):
        st.markdown(f"**Ruta actual de revisión:** `{reparto['ruta_nueva']}`")
        
        # Split layout: Left column for the form, Right column for the PDF viewer
        col_form, col_pdf = st.columns([1, 1])
        
        # ----------------- COLUMNA IZQUIERDA: FORMULARIO -----------------
        with col_form:
            st.markdown("##### 🛠️ Datos del Reparto")
            
            if is_blocked_for_operator:
                st.warning(
                    "🔒 **Edición Bloqueada para Operarios:** Este reparto fue devuelto a revisión para corrección de datos. "
                    "Por seguridad, **únicamente los usuarios Administradores** tienen autorización para editar sus datos y re-organizarlo."
                )
            elif es_devuelto and is_admin:
                st.info(
                    "ℹ️ **Reparto Devuelto a Revisión:** Estás editando este reparto con permisos de Administrador."
                )

            # Show motivo revision, missing, unsigned, excluded and found guias alerts
            if reparto.get("motivo_revision"):
                st.error(f"🛑 **Motivo de Revisión:** {reparto['motivo_revision']}")
            if reparto.get("guias_faltantes"):
                st.error(f"⚠️ **Guías Faltantes:** {reparto['guias_faltantes'].replace(',', ', ')}")
            if reparto.get("guias_sin_firma"):
                st.warning(f"✍️ **Guías Sin Firma:** {reparto['guias_sin_firma'].replace(',', ', ')}")
            if reparto.get("guias_no_entregadas"):
                st.info(f"🚫 **Guías No Entregadas (Marcadas 'NO' en Hoja):** {reparto['guias_no_entregadas'].replace(',', ', ')}")
            if reparto.get("guias_encontradas"):
                with st.expander("✅ Guías Encontradas"):
                    st.write(reparto["guias_encontradas"].replace(",", ", "))
            
            # Button to open the folder in File Explorer
            if st.button("📂 Abrir Carpeta en Explorador", key=f"open_rev_folder_{reparto['id']}", use_container_width=True):
                try:
                    res_open = requests.post(f"{API_URL}/api/repartos/{reparto['id']}/open")
                    if res_open.status_code == 200:
                        st.toast("Carpeta abierta en el Explorador.")
                    else:
                        st.error(res_open.json().get("detail", "Error al abrir la carpeta."))
                except Exception as ex:
                    st.error(f"Error de conexión: {ex}")

            unc_rev_p = get_network_unc_path(reparto.get("ruta_nueva") or reparto.get("ruta_original") or "")
            if unc_rev_p and unc_rev_p != (reparto.get("ruta_nueva") or reparto.get("ruta_original")):
                st.caption(f"🌐 **Ruta de Red:** `{unc_rev_p}`")

            empresa_options = ["INTERPROVINCIAL", "OTAPEYA"]
            default_empresa_idx = 0
            if reparto["empresa"] in empresa_options:
                default_empresa_idx = empresa_options.index(reparto["empresa"])
                
            empresa = st.selectbox(
                "Empresa", 
                options=empresa_options, 
                index=default_empresa_idx,
                disabled=is_blocked_for_operator,
                key=f"emp_{reparto['id']}"
            )
            
            # Default date parsing
            default_date = date.today()
            if reparto["fecha"]:
                try:
                    default_date = datetime.strptime(reparto["fecha"], "%Y-%m-%d").date()
                except ValueError:
                    pass
            
            fecha = st.date_input(
                "Fecha de Reparto", 
                value=default_date, 
                format="DD/MM/YYYY",
                disabled=is_blocked_for_operator,
                key=f"fecha_{reparto['id']}"
            )
            
            suc_clean_cur = (reparto.get("sucursal") or "").upper().strip()
            min_dig_hint = get_min_digits_for_sucursal(suc_clean_cur) if suc_clean_cur else 3
            valid_suc_list = ", ".join(settings.VALID_SUCURSALES.keys())

            sucursal = st.text_input(
                f"Sucursal ({valid_suc_list})", 
                value=reparto["sucursal"] if reparto["sucursal"] else "",
                placeholder="Ej. BB, CF, NQ, TD, VR, OL, GR, TA...",
                disabled=is_blocked_for_operator,
                key=f"suc_{reparto['id']}"
            )
            
            nro_reparto = st.text_input(
                f"Número de Reparto (Mínimo {min_dig_hint} dígitos para {suc_clean_cur or 'esta sucursal'})", 
                value=reparto["nro_reparto"] if reparto["nro_reparto"] else "",
                placeholder=f"Ej. {'138232' if min_dig_hint >= 6 else '12345'}",
                disabled=is_blocked_for_operator,
                key=f"num_{reparto['id']}"
            )
            
            # Resolution for missing guias
            resolucion_inputs = {}
            if reparto.get("guias_faltantes"):
                st.markdown("---")
                st.markdown("##### 🔍 Gestión de Guías Faltantes")
                st.info("Para cada guía que no se encontró físicamente, selecciona el motivo o ingresa una observación:")
                
                faltantes_list = [g.strip() for g in reparto["guias_faltantes"].split(",") if g.strip()]
                
                opciones_resolucion = [
                    "Guia Escaneada",
                    "Vuelta a Deposito",
                    "En REMISION",
                    "Numeración inexistente",
                    "Otro"
                ]
                
                for g in faltantes_list:
                    st.markdown(f"**Guía `{g}`:**")
                    col_est, col_obs = st.columns([1, 1])
                    with col_est:
                        estado_res = st.selectbox(
                            f"Estado / Motivo ({g})",
                            options=opciones_resolucion,
                            disabled=is_blocked_for_operator,
                            key=f"res_estado_{reparto['id']}_{g}"
                        )
                    with col_obs:
                        placeholder_obs = (
                            "Ej. Indicar número real de guía (ej. x.22.135744)..."
                            if estado_res == "Numeración inexistente"
                            else "Ej. Justificado por encargado..."
                        )
                        observacion = st.text_input(
                            f"Observación ({g})",
                            key=f"res_obs_{reparto['id']}_{g}",
                            disabled=is_blocked_for_operator,
                            placeholder=placeholder_obs
                        )
                        
                    resolucion_inputs[g] = {
                        "estado": estado_res,
                        "observacion": observacion
                    }

            # Resolution for unsigned guias
            resolucion_firma_inputs = {}
            if reparto.get("guias_sin_firma"):
                st.markdown("---")
                st.markdown("##### ✍️ Gestión de Guías Sin Firma")
                st.info("Las siguientes guías fueron digitalizadas pero **no tienen firma detectada**. Indica el motivo para autorizar el archivo:")
                
                sin_firma_list = [g.strip() for g in reparto["guias_sin_firma"].split(",") if g.strip()]
                
                opciones_firma = [
                    "Firma ilegible / Trazo tenue",
                    "Entregado con conformidad verbal / digital",
                    "Reclamar firma al chofer",
                    "Firma en otra hoja / anexo",
                    "Autorizado por supervisor"
                ]
                
                for g in sin_firma_list:
                    st.markdown(f"**Guía `{g}`:**")
                    col_est_f, col_obs_f = st.columns([1, 1])
                    with col_est_f:
                        estado_firma = st.selectbox(
                            f"Motivo sin firma ({g})",
                            options=opciones_firma,
                            disabled=is_blocked_for_operator,
                            key=f"res_firma_estado_{reparto['id']}_{g}"
                        )
                    with col_obs_f:
                        observacion_f = st.text_input(
                            f"Observación ({g})",
                            key=f"res_firma_obs_{reparto['id']}_{g}",
                            disabled=is_blocked_for_operator,
                            placeholder="Ej. Cliente autorizó por WhatsApp / Reclamar a chofer..."
                        )
                        
                    resolucion_firma_inputs[g] = {
                        "estado": estado_firma,
                        "observacion": observacion_f
                    }
            
            # Resolve button & duplicate override
            st.write("")
            permitir_duplicado = st.checkbox(
                "⚠️ Permitir guardar como duplicado / reimpresión", 
                key=f"dup_{reparto['id']}",
                disabled=is_blocked_for_operator,
                help="Tilda esta opción si ya existe otro reparto con el mismo número pero deseas guardarlo igualmente."
            )
            
            if is_blocked_for_operator:
                st.button("🔒 Edición reservada exclusivamente para Administradores", key=f"btn_blocked_{reparto['id']}", disabled=True, use_container_width=True)
            elif st.button("✓ Guardar y Organizar Carpeta", key=f"btn_{reparto['id']}", use_container_width=True):
                suc_clean = sucursal.strip().upper()
                is_valid_dig, act_dig, req_dig = validate_nro_reparto_digits(suc_clean, nro_reparto.strip())
                if not sucursal.strip() or not nro_reparto.strip():
                    st.error("Por favor completa los campos de Sucursal y Número de Reparto.")
                elif suc_clean not in settings.VALID_SUCURSALES:
                    valid_list = ", ".join(settings.VALID_SUCURSALES.keys())
                    st.error(f"Por favor ingresa una sucursal válida. Debe ser una de: {valid_list}")
                elif not is_valid_dig:
                    st.error(
                        f"El número de reparto para la sucursal {suc_clean} es incompleto o inválido. "
                        f"Requiere como mínimo {req_dig} dígitos numéricos (ingresaste: {act_dig})."
                    )
                else:
                    payload = {
                        "empresa": empresa,
                        "fecha": fecha.isoformat(),
                        "sucursal": sucursal.strip(),
                        "nro_reparto": nro_reparto.strip(),
                        "salida_path": salida_path.strip() if salida_path else None,
                        "resolucion_guias_faltantes": resolucion_inputs if resolucion_inputs else None,
                        "resolucion_guias_sin_firma": resolucion_firma_inputs if resolucion_firma_inputs else None,
                        "modo_historico": modo_historico,
                        "usuario_id": current_user.get("id") if current_user else None,
                        "usuario_legajo": current_user.get("legajo") if current_user else None,
                        "permitir_duplicado": permitir_duplicado
                    }
                    
                    try:
                        res = requests.post(f"{API_URL}/api/repartos/{reparto['id']}/resolve", json=payload)
                        if res.status_code == 200:
                            st.success("Carpeta organizada y guardada con éxito.")
                            on_resolve_callback()
                        else:
                            st.error(f"Error al procesar: {res.json().get('detail', 'Unknown error')}")
                    except Exception as e:
                        st.error(f"Error de conexión con el servidor: {e}")

            if is_admin:
                st.write("")
                with st.popover("🗑️ Anular y Borrar Carpeta para Re-escanear", use_container_width=True):
                    st.markdown("##### ⚠️ Confirmar Anulación y Borrado Físico")
                    st.error(
                        "Esta acción cambiará el estado del reparto a **ANULADO** en la base de datos y "
                        "**eliminará definitivamente la carpeta física y sus PDFs de disco**, "
                        "permitiendo volver a escanear este reparto desde cero sin conflictos."
                    )
                    motivo_anul = st.text_input(
                        "Motivo de descarte:", 
                        value="Re-escaneo desde cero por escaneo defectuoso", 
                        key=f"motivo_anul_rev_{reparto['id']}"
                    )
                    confirm_del = st.checkbox(
                        "Confirmo la eliminación física permanente de los archivos en disco.", 
                        key=f"chk_anul_rev_{reparto['id']}"
                    )
                    if st.button("🚨 Eliminar Definitivamente y Anular", key=f"btn_anular_rev_{reparto['id']}", type="primary", disabled=not confirm_del, use_container_width=True):
                        try:
                            payload_anul = {
                                "usuario_id": current_user.get("id") if current_user else None,
                                "usuario_legajo": current_user.get("legajo") if current_user else None,
                                "motivo": motivo_anul.strip() if motivo_anul else "Anulado para re-escaneo"
                            }
                            res_a = requests.post(f"{API_URL}/api/repartos/{reparto['id']}/anular", json=payload_anul)
                            if res_a.status_code == 200:
                                st.toast(f"✅ Reparto #{reparto.get('nro_reparto') or reparto['id']} anulado y eliminado del disco.")
                                on_resolve_callback()
                            else:
                                st.error(res_a.json().get("detail", "Error al anular reparto."))
                        except Exception as ex_an:
                            st.error(f"Error de conexión: {ex_an}")
                        
        # ----------------- COLUMNA DERECHA: VISOR DE PDF -----------------
        with col_pdf:
            st.markdown("##### 📄 Visor de PDF")
            
            # Scan for PDF files in the revision directory
            pdf_files = []
            if folder_path.exists() and folder_path.is_dir():
                pdf_files = sorted(list(folder_path.glob("*.pdf")), key=lambda p: p.name)
                
            if not pdf_files:
                st.warning("No se encontraron archivos PDF en esta carpeta.")
            else:
                # File selector if multiple PDFs exist
                pdf_options = {p.name: p for p in pdf_files}
                selected_pdf_name = st.selectbox(
                    "Archivo PDF:", 
                    options=list(pdf_options.keys()), 
                    key=f"pdf_sel_{reparto['id']}",
                    label_visibility="collapsed" if len(pdf_files) == 1 else "visible"
                )
                
                selected_pdf_path = pdf_options[selected_pdf_name]
                
                # Direct full-tab link in Chrome
                st.markdown(
                    f"<a href='{API_URL}/api/repartos/{reparto['id']}/files/{selected_pdf_name}' target='_blank' style='display:inline-block; margin-bottom: 8px; font-size: 0.85rem; color: #3b82f6; text-decoration: none; font-weight: bold;'>🔗 Abrir este PDF en pestaña completa de Chrome</a>",
                    unsafe_allow_html=True
                )
                
                try:
                    # Open the PDF using PyMuPDF (fitz)
                    doc = fitz.open(selected_pdf_path)
                    num_pages = len(doc)
                    
                    # Page selection controls
                    if num_pages > 1:
                        page_num = st.number_input(
                            f"Página (1-{num_pages}):",
                            min_value=1,
                            max_value=num_pages,
                            value=1,
                            key=f"pdf_page_{reparto['id']}"
                        )
                    else:
                        page_num = 1
                        
                    # Render page to PNG bytes with high clarity
                    page = doc[page_num - 1]
                    pix = page.get_pixmap(dpi=160) # render page to image with crisp DPI
                    img_data = pix.tobytes("png")
                    b64_img = base64.b64encode(img_data).decode("utf-8")
                    doc.close()
                    
                    # Display the interactive pan & zoom viewer
                    render_interactive_pdf_viewer(b64_img, height=580)
                    
                except Exception as pdf_err:
                    st.error(f"Error al abrir o renderizar el PDF: {pdf_err}")

def render_metrics_tab(current_user: dict, api_url: str):
    """Renders the dedicated Admin Metrics & Productivity tab with operational KPIs and PDF export."""
    from datetime import date, datetime, timedelta
    import pandas as pd
    from services.metrics_service import (
        generate_metrics_pdf, 
        generate_missing_repartos_pdf,
        generate_audit_report_pdf
    )


    st.markdown("### 📊 Rendimiento de Producción y Productividad de Operadores")
    st.markdown(
        "Panel exclusivo para **Administradores**. Supervisión en tiempo real del desempeño del OCR, "
        "volumen de digitalización diario y rendimiento individual de los puestos de escáner."
    )

    # 1. Filter bar & PDF export button
    c_filt, c_custom1, c_custom2, c_btn = st.columns([2, 1.2, 1.2, 1.6])
    with c_filt:
        periodo_opcion = st.selectbox(
            "📅 Período de Análisis:",
            options=["Histórico Total", "Hoy", "Últimos 7 días", "Este Mes", "Rango Personalizado"],
            index=0,
            key="metrics_periodo_sel"
        )
    
    desde = None
    hasta = None
    today = date.today()

    if periodo_opcion == "Hoy":
        desde = today
        hasta = today
    elif periodo_opcion == "Últimos 7 días":
        desde = today - timedelta(days=7)
        hasta = today
    elif periodo_opcion == "Este Mes":
        desde = today.replace(day=1)
        hasta = today
    elif periodo_opcion == "Rango Personalizado":
        with c_custom1:
            desde = st.date_input("Desde:", value=today - timedelta(days=30), key="metrics_desde")
        with c_custom2:
            hasta = st.date_input("Hasta:", value=today, key="metrics_hasta")

    # Fetch data from API
    params = {}
    if desde:
        params["desde"] = desde.isoformat()
    if hasta:
        params["hasta"] = hasta.isoformat()

    try:
        res = requests.get(f"{api_url}/api/metrics", params=params, timeout=10)
        if res.status_code == 200:
            m_data = res.json()
        else:
            st.error(f"Error al obtener métricas del servidor: {res.text}")
            return
    except Exception as ex:
        st.error(f"Error de conexión con el backend: {ex}")
        return

    # Export PDF button in c_btn
    with c_btn:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        label_filt = periodo_opcion if periodo_opcion != "Rango Personalizado" else f"{desde} a {hasta}"
        pdf_bytes = generate_metrics_pdf(
            m_data, 
            filter_label=label_filt,
            admin_name=current_user.get("nombre", "Administrador")
        )
        st.download_button(
            label="📥 Exportar PDF",
            data=pdf_bytes,
            file_name=f"reporte_metricas_{today.strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
            help="Descargar informe oficial de gestión en formato PDF para presentación o auditoría."
        )

    st.markdown("---")

    # ---------------- PUNTO 1: PRODUCCIÓN Y RENDIMIENTO OPERATIVO ----------------
    st.markdown("#### 1. ⚙️ Indicadores de Rendimiento de Producción (OCR & Digitalización)")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f"""
            <div class="stat-card primary">
                <div class="stat-value" style="color: #3b82f6;">{m_data.get('total_procesados', 0)}</div>
                <div class="stat-label">Total Digitalizados</div>
            </div>
            """, 
            unsafe_allow_html=True
        )
    with col2:
        eff = m_data.get('tasa_ocr_exito', 100.0)
        eff_color = "#10b981" if eff >= 90 else ("#f59e0b" if eff >= 75 else "#ef4444")
        st.markdown(
            f"""
            <div class="stat-card organized">
                <div class="stat-value" style="color: {eff_color};">{eff}%</div>
                <div class="stat-label">Éxito Automático OCR</div>
            </div>
            """, 
            unsafe_allow_html=True
        )
    with col3:
        st.markdown(
            f"""
            <div class="stat-card info">
                <div class="stat-value" style="color: #06b6d4;">{m_data.get('hoy_procesados', 0)}</div>
                <div class="stat-label">Digitalizados Hoy</div>
            </div>
            """, 
            unsafe_allow_html=True
        )
    with col4:
        rev_count = m_data.get('en_revision', 0)
        rev_color = "#10b981" if rev_count == 0 else "#f59e0b"
        st.markdown(
            f"""
            <div class="stat-card revision">
                <div class="stat-value" style="color: {rev_color};">{rev_count}</div>
                <div class="stat-label">Requieren Revisión</div>
            </div>
            """, 
            unsafe_allow_html=True
        )

    # Submetrics strip
    st.markdown("<br>", unsafe_allow_html=True)
    c_sub1, c_sub2, c_sub3, c_sub4 = st.columns(4)
    with c_sub1:
        st.caption(f"📅 **Esta semana:** {m_data.get('semana_procesados', 0)} repartos")
    with c_sub2:
        st.caption(f"🗓️ **Este mes:** {m_data.get('mes_procesados', 0)} repartos")
    with c_sub3:
        st.caption(f"⚡ **Promedio diario:** {m_data.get('promedio_diario', 0)} rep/día")
    with c_sub4:
        st.caption(f"📆 **Días activos registrados:** {m_data.get('dias_activos', 0)} días")

    # Daily evolution chart
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("##### 📈 Evolución Cronológica de Digitalización")
        evol_data = m_data.get("evolucion_diaria", [])
        if evol_data:
            df_evol = pd.DataFrame(evol_data)
            df_evol = df_evol.rename(columns={
                "organizados": "Organizados con Éxito",
                "revision": "Enviados a Revisión"
            })
            df_chart = df_evol.set_index("fecha")[["Organizados con Éxito", "Enviados a Revisión"]]
            st.bar_chart(df_chart, color=["#10b981", "#f59e0b"], use_container_width=True)
        else:
            st.info("No hay datos de evolución para el período seleccionado.")

    st.markdown("---")

    # ---------------- PUNTO 2: PRODUCTIVIDAD POR OPERADOR ----------------
    st.markdown("#### 2. 👤 Rendimiento y Productividad por Operador")
    st.markdown("Monitorea el caudal de trabajo procesado por cada miembro del equipo y su porcentaje de aporte a la digitalización.")

    operadores = m_data.get("operadores", [])
    if not operadores:
        st.info("No hay datos de operadores registrados para este período.")
    else:
        c_op_chart, c_op_table = st.columns([1.2, 1.8])
        
        # Chart
        with c_op_chart:
            with st.container(border=True):
                st.markdown("##### 🏆 Caudal por Operador")
                df_ops = pd.DataFrame(operadores)
                df_ops["Operador"] = df_ops["nombre"] + " (" + df_ops["legajo"] + ")"
                df_ops_chart = df_ops.set_index("Operador")[["total_procesados"]].rename(columns={"total_procesados": "Repartos Digitalizados"})
                st.bar_chart(df_ops_chart, color="#6366f1", use_container_width=True)

        # Table
        with c_op_table:
            with st.container(border=True):
                st.markdown("##### 📋 Desglose Detallado de Personal")
                
                for idx, op in enumerate(operadores):
                    medal = "🥇 " if idx == 0 and op['total_procesados'] > 0 else ("🥈 " if idx == 1 and op['total_procesados'] > 0 else "👤 ")
                    c_l1, c_l2, c_l3 = st.columns([3, 2, 2])
                    with c_l1:
                        st.markdown(f"**{medal}{op['nombre']}** (`Legajo {op['legajo']}`)")
                        st.caption(f"Rol: `{op['rol']}`")
                    with c_l2:
                        st.markdown(f"📁 **{op['total_procesados']}** procesados")
                        st.caption(f"✓ {op['organizados']} org. | ⚠️ {op['en_revision']} rev.")
                    with c_l3:
                        pct = op.get('porcentaje_participacion', 0.0)
                        st.markdown(f"**{pct}%** del total")
                        st.progress(min(pct / 100.0, 1.0))
                    if idx < len(operadores) - 1:
                        st.markdown("<hr style='margin: 6px 0; border: 0.5px solid #334155;'>", unsafe_allow_html=True)

    # ---------------- CONTEXTO LOGÍSTICO OPCIONAL ----------------
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("🏢 Distribución de Volumen por Sucursal y Empresa (Contexto Logístico)", expanded=False):
        c_suc, c_emp = st.columns(2)
        with c_suc:
            st.markdown("##### Top Sucursales Activas")
            sucs = m_data.get("sucursales", [])
            if sucs:
                df_sucs = pd.DataFrame(sucs).set_index("sucursal")
                st.bar_chart(df_sucs, color="#0ea5e9", use_container_width=True)
            else:
                st.caption("Sin datos.")
        with c_emp:
            st.markdown("##### Distribución por Empresa")
            emps = m_data.get("empresas", [])
            if emps:
                df_emps = pd.DataFrame(emps).set_index("empresa")
                st.bar_chart(df_emps, color="#a855f7", use_container_width=True)
            else:
                st.caption("Sin datos.")

    # ---------------- PUNTO 3: AUDITORÍA DE REPARTOS FALTANTES ----------------
    st.markdown("---")
    st.markdown("#### 3. 🔍 Auditoría de Repartos Faltantes (Control de Correlatividad)")
    st.markdown(
        "Detecta qué repartos faltan digitalizar analizando el intervalo entre el número de reparto "
        "**más bajo** y el **más alto** registrado en cada sucursal de forma 100% independiente."
    )

    # 1. Fetch available sucursales with their min and max
    try:
        r_sucs = requests.get(f"{api_url}/api/metrics/sucursales", timeout=10)
        sucs_stats = r_sucs.json() if r_sucs.status_code == 200 else []
    except Exception:
        sucs_stats = []

    if not sucs_stats:
        st.info("No hay sucursales con repartos registrados para analizar.")
    else:
        # Create sucursal options
        suc_map = {s["codigo"]: s for s in sucs_stats}
        suc_options = [s["codigo"] for s in sucs_stats]
        
        c_sel_suc, c_desde, c_hasta, c_pdf = st.columns([2, 1.2, 1.2, 1.8])
        
        with c_sel_suc:
            selected_suc_code = st.selectbox(
                "🏢 Seleccionar Sucursal a Auditar:",
                options=suc_options,
                format_func=lambda x: f"{x} - {suc_map[x]['nombre']} ({suc_map[x]['total_repartos']} digitalizados)",
                key="sel_suc_faltantes"
            )

        current_suc_info = suc_map[selected_suc_code]
        min_auto = current_suc_info["min_reparto"]
        max_auto = current_suc_info["max_reparto"]

        with c_desde:
            input_desde = st.number_input(
                "Reparto Desde (Mín):",
                min_value=1,
                value=int(min_auto),
                step=1,
                key=f"num_desde_{selected_suc_code}",
                help="Por defecto se toma el reparto más bajo detectado en la base de datos."
            )

        with c_hasta:
            input_hasta = st.number_input(
                "Reparto Hasta (Máx):",
                min_value=int(input_desde),
                value=int(max_auto),
                step=1,
                key=f"num_hasta_{selected_suc_code}",
                help="Por defecto se toma el reparto más alto detectado en la base de datos."
            )

        # Query faltantes for this sucursal & range
        try:
            r_falt = requests.get(
                f"{api_url}/api/metrics/faltantes",
                params={
                    "sucursal": selected_suc_code,
                    "desde": int(input_desde),
                    "hasta": int(input_hasta)
                },
                timeout=15
            )
            falt_data = r_falt.json() if r_falt.status_code == 200 else None
        except Exception as ex_f:
            st.error(f"Error al calcular repartos faltantes: {ex_f}")
            falt_data = None

        if falt_data:
            with c_pdf:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                pdf_falt_bytes = generate_missing_repartos_pdf(
                    falt_data,
                    admin_name=current_user.get("nombre", "Administrador")
                )
                st.download_button(
                    label=f"📥 Exportar Faltantes PDF ({selected_suc_code})",
                    data=pdf_falt_bytes,
                    file_name=f"faltantes_{selected_suc_code}_{input_desde}_{input_hasta}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary",
                    help="Descargar reporte oficial con el detalle de todos los tramos de repartos faltantes."
                )

            # KPI status cards
            col_k1, col_k2, col_k3, col_k4 = st.columns(4)
            with col_k1:
                st.markdown(
                    f"""
                    <div class="stat-card primary">
                        <div class="stat-value" style="color: #3b82f6;">{falt_data['total_en_rango']:,}</div>
                        <div class="stat-label">Total Teórico en Rango</div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            with col_k2:
                st.markdown(
                    f"""
                    <div class="stat-card organized">
                        <div class="stat-value" style="color: #10b981;">{falt_data['total_existentes']:,}</div>
                        <div class="stat-label">Digitalizados ({falt_data['porcentaje_cobertura']}%)</div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            with col_k3:
                st.markdown(
                    f"""
                    <div class="stat-card revision">
                        <div class="stat-value" style="color: #ef4444;">{falt_data['total_faltantes']:,}</div>
                        <div class="stat-label">Repartos Faltantes</div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            with col_k4:
                cant_tramos = len(falt_data.get('tramos', []))
                st.markdown(
                    f"""
                    <div class="stat-card purple">
                        <div class="stat-value" style="color: #a855f7;">{cant_tramos:,}</div>
                        <div class="stat-label">Tramos / Saltos Detectados</div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )

            st.markdown("<br>", unsafe_allow_html=True)

            # Sub-tabs for detailed gap exploration
            subtab_tramos, subtab_buscar, subtab_listado = st.tabs([
                f"📋 Tramos y Bloques Faltantes ({cant_tramos})",
                "🔎 Verificador de Reparto Específico",
                "🔢 Listado Numérico"
            ])

            with subtab_tramos:
                tramos_list = falt_data.get("tramos", [])
                if not tramos_list:
                    st.success(f"🎉 ¡Correlatividad 100% Completa! No falta ningún reparto entre #{input_desde} y #{input_hasta}.")
                else:
                    st.caption("A continuación se detallan los saltos e intervalos donde se detectaron faltantes:")
                    
                    df_tramos = pd.DataFrame(tramos_list)
                    df_tramos["Tipo"] = df_tramos["cantidad"].apply(lambda c: "Individual (1 número)" if c == 1 else f"Bloque ({c:,} números)")
                    df_tramos["Desde"] = df_tramos["desde"].apply(lambda x: f"#{x}")
                    df_tramos["Hasta"] = df_tramos["hasta"].apply(lambda x: f"#{x}")
                    df_tramos = df_tramos.rename(columns={"cantidad": "Cantidad Faltante"})
                    df_tramos.index = df_tramos.index + 1
                    df_tramos.index.name = "N°"
                    
                    st.dataframe(
                        df_tramos[["Desde", "Hasta", "Cantidad Faltante", "Tipo"]],
                        use_container_width=True,
                        height=350
                    )

            with subtab_buscar:
                st.markdown("##### 🔎 Consultar si un Reparto está Digitalizado o Faltante")
                nro_query = st.number_input(
                    f"Ingrese número de reparto de {selected_suc_code}:",
                    min_value=1,
                    value=int(input_desde),
                    step=1,
                    key="query_single_reparto"
                )
                
                # Check status
                is_missing = False
                tramos_match = None
                for t in falt_data.get("tramos", []):
                    if t["desde"] <= nro_query <= t["hasta"]:
                        is_missing = True
                        tramos_match = t
                        break

                if nro_query < input_desde or nro_query > input_hasta:
                    st.info(f"El reparto #{nro_query} está fuera del rango actualmente evaluado (#{input_desde} a #{input_hasta}).")
                elif is_missing:
                    st.error(
                        f"⚠️ **REPARTO #{nro_query} FALTANTE:** Este reparto NO ha sido digitalizado aún en la sucursal {selected_suc_code}.\n\n"
                        f"Pertenece al tramo faltante desde **#{tramos_match['desde']}** hasta **#{tramos_match['hasta']}** ({tramos_match['cantidad']:,} faltantes en ese bloque)."
                    )
                else:
                    st.success(f"✅ **REPARTO #{nro_query} DIGITALIZADO:** Este reparto se encuentra registrado y organizado correctamente en la base de datos.")

            with subtab_listado:
                st.markdown("##### 🔢 Muestra de Números Faltantes Individuales")
                nums_list = falt_data.get("numeros_faltantes", [])
                if not nums_list:
                    st.success("No hay repartos faltantes.")
                else:
                    tot_all_missing = falt_data.get("total_numeros_faltantes", len(nums_list))
                    if tot_all_missing > len(nums_list):
                        st.info(f"Mostrando los primeros {len(nums_list):,} de {tot_all_missing:,} números faltantes (para descargar el informe completo de todos los tramos, utilice el botón de PDF arriba).")
                    
                    search_txt = st.text_input("Filtrar lista de números:", placeholder="Ej. 1578", key="filter_missing_nums")
                    filtered_nums = [n for n in nums_list if search_txt in str(n)] if search_txt else nums_list
                    
                    formatted_pills = " ".join([f"<span style='background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); padding: 3px 8px; border-radius: 6px; font-weight: 600; font-size: 0.85rem; margin: 2px; display: inline-block;'>#{n}</span>" for n in filtered_nums[:300]])
                    st.markdown(f"<div style='max-height: 250px; overflow-y: auto; padding: 10px; background: #0f172a; border-radius: 8px; border: 1px solid #334155;'>{formatted_pills}</div>", unsafe_allow_html=True)
                    if len(filtered_nums) > 300:
                        st.caption(f"Mostrando 300 de {len(filtered_nums)} números coincidentes.")

    # ---------------- PUNTO 4: AUDITORÍA MANUAL DE INTEGRIDAD (DISCO VS BD) ----------------
    st.markdown("---")
    st.markdown("#### 4. 🛡️ Auditoría de Integridad: Almacenamiento Físico vs. Base de Datos")
    st.markdown(
        "Ejecuta un control cruzado manual para comparar cada registro de la base de datos contra el almacenamiento físico en disco. "
        "Permite auditar los repartos del **último año** (365 días) o el **histórico completo** para detectar carpetas faltantes o vacías."
    )

    c_audit_btn1, c_audit_btn2, c_audit_pdf = st.columns([1.3, 1.4, 1.8])
    with c_audit_btn1:
        btn_audit_year = st.button("📅 Auditoría (Último Año)", use_container_width=True, key="btn_run_integrity_audit_year", help="Auditar integridad física de repartos desde hace 1 año hasta la fecha.")
    with c_audit_btn2:
        btn_audit_total = st.button("🚀 Auditoría Total (Histórico)", type="primary", use_container_width=True, key="btn_run_integrity_audit_total", help="Auditar integridad física de todos los repartos registrados históricamente.")

    if btn_audit_year:
        with st.spinner("Auditando integridad física y base de datos (Último Año - 365 días)..."):
            try:
                r_aud = requests.post(f"{api_url}/api/metrics/audit/run", params={"dias_atras": 365}, timeout=90)
                if r_aud.status_code == 200:
                    st.session_state["audit_results"] = r_aud.json()
                    st.session_state["audit_scope_label"] = "ultimo_ano"
                    st.toast("Auditoría del último año completada con éxito.")
                else:
                    st.error(f"Error al ejecutar auditoría: {r_aud.text}")
            except Exception as ex_a:
                st.error(f"Error de conexión con el backend: {ex_a}")

    if btn_audit_total:
        with st.spinner("Auditando integridad física y base de datos (Histórico Completo)..."):
            try:
                r_aud = requests.post(f"{api_url}/api/metrics/audit/run", timeout=90)
                if r_aud.status_code == 200:
                    st.session_state["audit_results"] = r_aud.json()
                    st.session_state["audit_scope_label"] = "historico_completo"
                    st.toast("Auditoría histórica completa completada con éxito.")
                else:
                    st.error(f"Error al ejecutar auditoría: {r_aud.text}")
            except Exception as ex_a:
                st.error(f"Error de conexión con el backend: {ex_a}")

    audit_res = st.session_state.get("audit_results")
    if audit_res:
        with c_audit_pdf:
            pdf_aud_bytes = generate_audit_report_pdf(
                audit_res,
                admin_name=current_user.get("nombre", "Administrador")
            )
            scope_prefix = st.session_state.get("audit_scope_label", "auditoria")
            st.download_button(
                label="📥 Descargar Informe en PDF",
                data=pdf_aud_bytes,
                file_name=f"auditoria_integridad_{scope_prefix}_{today.strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True,
                type="primary",
                help="Descargar el informe oficial en PDF detallando todas las irregularidades encontradas."
            )

        # Status alert
        tot_irregs = audit_res.get("total_irregularidades", 0)
        periodo_txt = audit_res.get('desde', 'Histórico Completo')
        if periodo_txt != 'Histórico Completo' and audit_res.get('hasta'):
            periodo_txt = f"{periodo_txt} al {audit_res.get('hasta')}"

        if tot_irregs == 0:
            st.success(
                f"✅ **¡Auditoría 100% Exitosa!** Se evaluaron **{audit_res['total_evaluados']:,}** repartos ({periodo_txt}) "
                f"y todos cuentan con sus archivos físicos en disco."
            )
        else:
            st.warning(
                f"⚠️ **Auditoría completada:** Se detectaron **{tot_irregs:,} irregularidades** en los {audit_res['total_evaluados']:,} "
                f"repartos evaluados ({periodo_txt})."
            )

        if audit_res.get("unidades_estado"):
            st.caption(f"💾 **Estado de unidades:** {audit_res['unidades_estado']}")


        # KPI cards
        c_a1, c_a2, c_a3, c_a4 = st.columns(4)
        with c_a1:
            st.markdown(
                f"""
                <div class="stat-card primary">
                    <div class="stat-value" style="color: #3b82f6;">{audit_res['total_evaluados']:,}</div>
                    <div class="stat-label">Evaluados en BD</div>
                </div>
                """, 
                unsafe_allow_html=True
            )
        with c_a2:
            st.markdown(
                f"""
                <div class="stat-card organized">
                    <div class="stat-value" style="color: #10b981;">{audit_res['verificados_ok']:,}</div>
                    <div class="stat-label">Verificados en Disco</div>
                </div>
                """, 
                unsafe_allow_html=True
            )
        with c_a3:
            color_irr = "#ef4444" if tot_irregs > 0 else "#10b981"
            st.markdown(
                f"""
                <div class="stat-card revision">
                    <div class="stat-value" style="color: {color_irr};">{tot_irregs:,}</div>
                    <div class="stat-label">Irregularidades</div>
                </div>
                """, 
                unsafe_allow_html=True
            )
        with c_a4:
            st.markdown(
                f"""
                <div class="stat-card purple">
                    <div class="stat-value" style="color: #8b5cf6;">{audit_res['tasa_integridad']}%</div>
                    <div class="stat-label">Integridad Física</div>
                </div>
                """, 
                unsafe_allow_html=True
            )

        # Table of irregularities
        irreg_list = audit_res.get("irregularidades", [])
        if irreg_list:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown(f"##### ⚠️ Listado de Irregularidades ({len(irreg_list):,})")
                
                df_irr = pd.DataFrame(irreg_list)
                df_irr["Tipo"] = df_irr["tipo"].apply(
                    lambda t: "❌ Faltante en Disco" if t == "FALTANTE_EN_DISCO" else ("⚠️ Carpeta Vacía (0 PDFs)" if t == "CARPETA_VACIA" else t)
                )
                df_irr["Reparto"] = df_irr["reparto"].apply(lambda r: f"#{r}")
                df_irr = df_irr.rename(columns={
                    "reparto": "Código",
                    "fecha": "Fecha Reparto",
                    "descripcion": "Descripción del Problema",
                    "ruta_esperada": "Ruta Esperada"
                })
                df_irr.index = df_irr.index + 1
                df_irr.index.name = "N°"
                
                st.dataframe(
                    df_irr[["Código", "Fecha Reparto", "Tipo", "Descripción del Problema", "Ruta Esperada"]],
                    use_container_width=True,
                    height=350
                )




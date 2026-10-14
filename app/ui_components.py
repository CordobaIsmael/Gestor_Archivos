import streamlit as st
import streamlit.components.v1 as components
import requests
import base64
from datetime import date, datetime
from pathlib import Path
import fitz  # PyMuPDF
from config.settings import settings
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
    
    with st.expander(f"📁 {folder_name} (ID: {reparto['id']})", expanded=is_active):
        st.markdown(f"**Ruta actual de revisión:** `{reparto['ruta_nueva']}`")
        
        # Split layout: Left column for the form, Right column for the PDF viewer
        col_form, col_pdf = st.columns([1, 1])
        
        # ----------------- COLUMNA IZQUIERDA: FORMULARIO -----------------
        with col_form:
            st.markdown("##### 🛠️ Datos del Reparto")
            
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
                key=f"fecha_{reparto['id']}"
            )
            
            sucursal = st.text_input(
                "Sucursal (MP, TA, CO, OL, VR, RC, CH, BB, CF, NQ, RO, AZ)", 
                value=reparto["sucursal"] if reparto["sucursal"] else "",
                placeholder="Ej. MP, TA, VR, RC, CH...",
                key=f"suc_{reparto['id']}"
            )
            
            nro_reparto = st.text_input(
                "Número de Reparto", 
                value=reparto["nro_reparto"] if reparto["nro_reparto"] else "",
                placeholder="Ej. 138232",
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
                    "Otro"
                ]
                
                for g in faltantes_list:
                    st.markdown(f"**Guía `{g}`:**")
                    col_est, col_obs = st.columns([1, 1])
                    with col_est:
                        estado_res = st.selectbox(
                            f"Estado / Motivo ({g})",
                            options=opciones_resolucion,
                            key=f"res_estado_{reparto['id']}_{g}"
                        )
                    with col_obs:
                        observacion = st.text_input(
                            f"Observación ({g})",
                            key=f"res_obs_{reparto['id']}_{g}",
                            placeholder="Ej. Justificado por encargado..."
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
                            key=f"res_firma_estado_{reparto['id']}_{g}"
                        )
                    with col_obs_f:
                        observacion_f = st.text_input(
                            f"Observación ({g})",
                            key=f"res_firma_obs_{reparto['id']}_{g}",
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
                help="Tilda esta opción si ya existe otro reparto con el mismo número pero deseas guardarlo igualmente."
            )
            
            if st.button("✓ Guardar y Organizar Carpeta", key=f"btn_{reparto['id']}", use_container_width=True):
                suc_clean = sucursal.strip().upper()
                if not sucursal.strip() or not nro_reparto.strip():
                    st.error("Por favor completa los campos de Sucursal y Número de Reparto.")
                elif suc_clean not in settings.VALID_SUCURSALES:
                    valid_list = ", ".join(settings.VALID_SUCURSALES.keys())
                    st.error(f"Por favor ingresa una sucursal válida. Debe ser una de: {valid_list}")
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

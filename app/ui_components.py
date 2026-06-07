import streamlit as st
import requests
from datetime import date
from pathlib import Path
import fitz  # PyMuPDF
from config.settings import settings

API_URL = settings.API_URL

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

def render_reparto_row(reparto: dict, on_resolve_callback, active_caja=None):
    """Renders an interactive manual editor and PDF viewer inside a collapsible container for Revision items."""
    folder_path = Path(reparto['ruta_nueva'])
    folder_name = folder_path.name
    
    with st.expander(f"📁 {folder_name} (ID: {reparto['id']})"):
        st.markdown(f"**Ruta actual de revisión:** `{reparto['ruta_nueva']}`")
        
        # Split layout: Left column for the form, Right column for the PDF viewer
        col_form, col_pdf = st.columns([1, 1])
        
        # ----------------- COLUMNA IZQUIERDA: FORMULARIO -----------------
        with col_form:
            st.markdown("##### 🛠️ Datos del Reparto")
            if active_caja is None:
                st.warning("⚠️ Debes tener una caja activa abierta para guardar y organizar este reparto.")
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
                    default_date = date.fromisoformat(reparto["fecha"])
                except Exception:
                    pass
            
            fecha = st.date_input(
                "Fecha de Reparto", 
                value=default_date,
                key=f"fec_{reparto['id']}"
            )
            
            sucursal = st.text_input(
                "Sucursal (BB, NQN, CF, MDP, etc.)", 
                value=reparto["sucursal"] or "",
                key=f"suc_{reparto['id']}"
            )
            
            nro_reparto = st.text_input(
                "Número de Reparto", 
                value=reparto["nro_reparto"] or "",
                key=f"nro_{reparto['id']}"
            )
            
            # Resolve button
            st.write("")
            if st.button("✓ Guardar y Organizar Carpeta", key=f"btn_{reparto['id']}", use_container_width=True, disabled=active_caja is None):
                if not sucursal.strip() or not nro_reparto.strip():
                    st.error("Por favor completa los campos de Sucursal y Número de Reparto.")
                else:
                    payload = {
                        "empresa": empresa,
                        "fecha": fecha.isoformat(),
                        "sucursal": sucursal.strip(),
                        "nro_reparto": nro_reparto.strip()
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
                pdf_files = list(folder_path.glob("*.pdf"))
                
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
                        
                    # Render page to PNG bytes
                    page = doc[page_num - 1]
                    pix = page.get_pixmap(dpi=130) # render page to image
                    img_data = pix.tobytes("png")
                    
                    # Display the rendered image
                    st.image(img_data, use_container_width=True)
                    doc.close()
                    
                except Exception as pdf_err:
                    st.error(f"Error al abrir o renderizar el PDF: {pdf_err}")

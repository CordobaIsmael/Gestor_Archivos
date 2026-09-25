import os
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and print total page count."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8.5)
        self.setFillColor(colors.HexColor("#475569"))
        
        # Header (Pages > 1)
        if self._pageNumber > 1:
            self.drawString(45, 11 * inch - 30, "GestorArchivo — Manual de Uso Práctico")
            self.setFont("Helvetica", 8.5)
            self.setFillColor(colors.HexColor("#94a3b8"))
            self.drawRightString(8.5 * inch - 45, 11 * inch - 30, "Operaciones y Digitalización")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(45, 11 * inch - 34, 8.5 * inch - 45, 11 * inch - 34)
            
        # Footer
        self.setFont("Helvetica", 8.5)
        self.setFillColor(colors.HexColor("#64748b"))
        text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(8.5 * inch - 45, 26, text)
        self.drawString(45, 26, "GestorArchivo — Guía para Operadores y Personal Administrativo")
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(45, 36, 8.5 * inch - 45, 36)
        
        self.restoreState()

def generate_pdf(output_path: Path):
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=45,
        rightMargin=45,
        topMargin=40,
        bottomMargin=46
    )

    styles = getSampleStyleSheet()
    
    # Typography styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        alignment=TA_LEFT
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#4338ca"),
        alignment=TA_LEFT,
        spaceAfter=6
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=15,
        textColor=colors.HexColor("#1e1b4b"),
        spaceBefore=11,
        spaceAfter=5,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.2,
        leading=13.5,
        textColor=colors.HexColor("#334155"),
        spaceAfter=4
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=14,
        firstLineIndent=-9,
        spaceAfter=4
    )

    callout_style = ParagraphStyle(
        'Callout_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.2,
        leading=13.5,
        textColor=colors.HexColor("#312e81")
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.8,
        leading=11,
        textColor=colors.white,
        alignment=TA_CENTER
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1e293b"),
        alignment=TA_LEFT
    )

    table_code_style = ParagraphStyle(
        'TableCode',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#4338ca"),
        alignment=TA_CENTER
    )

    story = []

    # ----------------- PÁGINA 1 -----------------
    story.append(Paragraph("Manual de Uso — Gestor de Repartos", title_style))
    story.append(Paragraph("Guía práctica paso a paso para digitalización y archivo de documentos", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor("#4f46e5"), spaceAfter=10))

    # Intro Callout Box
    intro_text = (
        "<b>Objetivo del programa:</b> Este sistema lee automáticamente las hojas de reparto y remitos "
        "escaneados, controla firmas y documentos faltantes, y los guarda clasificados y ordenados en el disco "
        "de archivo (Interprovincial u Otapeya)."
    )
    intro_table = Table(
        [[Paragraph(intro_text, callout_style)]],
        colWidths=[522]
    )
    intro_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#eef2ff")),
        ('BORDER', (0,0), (-1,-1), 0.8, colors.HexColor("#c7d2fe")),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(intro_table)
    story.append(Spacer(1, 6))

    # 1. Abrir el programa
    story.append(Paragraph("1. Cómo abrir y cerrar el programa", h1_style))
    story.append(Paragraph("• <b>Para abrir:</b> Haz doble clic en el archivo <b>iniciar.cmd</b>. Se abrirá automáticamente tu navegador web con la pantalla del sistema.", bullet_style))
    story.append(Paragraph("• <b>Para cerrar:</b> Al finalizar tu turno, haz doble clic en <b>detener.cmd</b> para apagar el sistema de forma segura.", bullet_style))

    # 2. Iniciar sesión
    story.append(Paragraph("2. Cómo iniciar sesión", h1_style))
    story.append(Paragraph("1. Escribe tu <b>Número de Legajo / Usuario</b> (por ejemplo: <code>1101</code>).", bullet_style))
    story.append(Paragraph("2. Escribe tu <b>Contraseña o DNI</b> y presiona <b>'Iniciar Sesión'</b>.", bullet_style))
    story.append(Paragraph("<i>Nota: Para cambiar tu clave personal, haz clic en el botón <b>[Clave]</b> en el menú lateral izquierdo.</i>", body_style))

    # 3. Organizar repartos
    story.append(Paragraph("3. Cómo organizar los repartos escaneados (Trabajo Diario)", h1_style))
    story.append(Paragraph("<b>Paso 1: Colocar los archivos:</b> Pon las carpetas que salieron del escáner adentro de la carpeta <b>Entrada</b>.", bullet_style))
    story.append(Paragraph("<b>Paso 2: Elegir el modo:</b> En la barra izquierda, deja seleccionado <b>'Operación Estándar'</b> (es el modo habitual que controla firmas y remitos).", bullet_style))
    story.append(Paragraph("<b>Paso 3: Procesar:</b> Haz clic en el botón violeta <b>[Procesar Entrada]</b>.", bullet_style))
    story.append(Paragraph("• Si la hoja se leyó bien y está completa, <b>se guarda sola</b> en la carpeta que corresponda (<b>Interprovincial</b> u <b>Otapeya</b>).", bullet_style))
    story.append(Paragraph("• Si la hoja estaba borrosa o faltó alguna firma, pasará a la pestaña <b>'En Revisión'</b> para que la completes.", bullet_style))

    # 4. Revisión manual
    story.append(Paragraph("4. ¿Qué hacer si un reparto fue a 'En Revisión'?", h1_style))
    story.append(Paragraph("1. Haz clic en la pestaña <b>'En Revisión'</b> (arriba en la pantalla) y despliega la carpeta a revisar.", bullet_style))
    story.append(Paragraph("2. <b>Visor a la derecha:</b> Puedes ver la hoja escaneada en pantalla para leer los datos que falten.", bullet_style))
    story.append(Paragraph("3. <b>Formulario a la izquierda:</b> Completa o confirma la información:", bullet_style))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• <b>Empresa:</b> Selecciona <i>INTERPROVINCIAL</i> u <i>OTAPEYA</i>.", bullet_style))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• <b>Fecha:</b> La fecha que figura en la hoja.", bullet_style))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• <b>Sucursal:</b> Las 2 letras de la ciudad (ver tabla en página 2).", bullet_style))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• <b>Número de Reparto:</b> El número identificador del reparto.", bullet_style))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• <b>Firma o remito faltante:</b> Si hubo novedades, elige el motivo en la lista desplegable.", bullet_style))
    story.append(Paragraph("4. Haz clic en <b>'Guardar y Organizar Carpeta'</b>. El reparto quedará archivado correctamente.", bullet_style))

    # ----------------- SALTO A PÁGINA 2 -----------------
    story.append(PageBreak())

    # 5. Tabla de sucursales
    story.append(Paragraph("5. Códigos oficiales de Sucursales (Ciudades)", h1_style))
    story.append(Paragraph("Cuando tengas que ingresar una sucursal manualmente, utiliza exactamente estas siglas:", body_style))
    
    table_data = [
        [Paragraph("Sigla", table_header_style), Paragraph("Ciudad / Sucursal", table_header_style), Paragraph("Carpeta en Disco", table_header_style),
         Paragraph("Sigla", table_header_style), Paragraph("Ciudad / Sucursal", table_header_style), Paragraph("Carpeta en Disco", table_header_style)],
        [Paragraph("MP", table_code_style), Paragraph("Mar del Plata", table_cell_style), Paragraph("MAR_DEL_PLATA", table_cell_style),
         Paragraph("CH", table_code_style), Paragraph("Choele Choel", table_cell_style), Paragraph("CHOELE_CHOEL", table_cell_style)],
        [Paragraph("TA", table_code_style), Paragraph("Tres Arroyos", table_cell_style), Paragraph("TRES_ARROYOS", table_cell_style),
         Paragraph("BB", table_code_style), Paragraph("Bahía Blanca", table_cell_style), Paragraph("BAHIA_BLANCA", table_cell_style)],
        [Paragraph("CO", table_code_style), Paragraph("Córdoba", table_cell_style), Paragraph("CORDOBA", table_cell_style),
         Paragraph("CF", table_code_style), Paragraph("Capital Federal", table_cell_style), Paragraph("CAPITAL_FEDERAL", table_cell_style)],
        [Paragraph("OL", table_code_style), Paragraph("Olavarría", table_cell_style), Paragraph("OLAVARRIA", table_cell_style),
         Paragraph("NQ", table_code_style), Paragraph("Neuquén", table_cell_style), Paragraph("NEUQUEN", table_cell_style)],
        [Paragraph("VR", table_code_style), Paragraph("Villa Regina", table_cell_style), Paragraph("VILLA_REGINA", table_cell_style),
         Paragraph("RO", table_code_style), Paragraph("Rosario", table_cell_style), Paragraph("ROSARIO", table_cell_style)],
        [Paragraph("RC", table_code_style), Paragraph("Río Colorado", table_cell_style), Paragraph("RIO_COLORADO", table_cell_style),
         Paragraph("AZ", table_code_style), Paragraph("Azul", table_cell_style), Paragraph("AZUL", table_cell_style)],
    ]

    suc_table = Table(table_data, colWidths=[48, 104, 109, 48, 104, 109])
    suc_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#312e81")),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(suc_table)
    story.append(Spacer(1, 6))

    # 6. Buscar repartos
    story.append(Paragraph("6. Cómo buscar un reparto o remito viejo", h1_style))
    story.append(Paragraph("Cuando un chofer, cliente o supervisor te pida consultar un documento archivado:", body_style))
    story.append(Paragraph("1. Ve a la pestaña <b>'Buscar Reparto'</b>.", bullet_style))
    story.append(Paragraph("2. En el casillero de búsqueda escribe el <b>número de reparto</b> (ej: <code>138232</code>), el <b>número de guía/remito</b> (ej: <code>845563</code>) o la <b>sucursal</b>.", bullet_style))
    story.append(Paragraph("3. En el resultado obtenido podrás:", bullet_style))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• Ver de un vistazo si el remito fue entregado, si faltaba o si no tenía firma.", bullet_style))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• Hacer clic en <b>'Explorador Local'</b> para abrir la carpeta directamente en Windows.", bullet_style))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• Hacer clic en <b>'Ver PDF'</b> para abrir y leer el documento en tu pantalla.", bullet_style))

    # 7. Exportar a Excel
    story.append(Paragraph("7. Cómo descargar reportes en Excel", h1_style))
    story.append(Paragraph("1. Ve a la pestaña <b>'Organizados'</b>.", bullet_style))
    story.append(Paragraph("2. Arriba a la derecha haz clic en el botón <b>[Exportar a Excel (.xlsx)]</b>.", bullet_style))
    story.append(Paragraph("3. Se descargará de inmediato una planilla con el historial completo de los repartos digitalizados, con sus fechas, sucursales, operador responsable y detalle de novedades.", bullet_style))

    # 8. Preguntas Frecuentes y Consejos Útiles
    story.append(Paragraph("8. Preguntas Frecuentes y Solución de Dudas", h1_style))
    
    faq_box_1 = (
        "<b>¿Dónde se consultan los archivos organizados?</b><br/>"
        "Los usuarios consultan y abren los archivos desde los discos espejo de consulta: <b>Q:\\AD_INTERPROVINCIAL</b> y <b>O:\\AD_OTAPEYA</b> "
        "(sincronizados automáticamente cada 1 hora), protegiendo los originales maestros del disco A:\\."
    )
    faq_box_2 = (
        "<b>¿Qué hago si aparece el cartel de 'Posible Duplicado'?</b><br/>"
        "Significa que ya existe en el sistema un reparto con ese mismo número y sucursal. Si se trata de una reimpresión "
        "o reenvío válido, puedes tildar la opción <i>'Permitir guardar como duplicado'</i> y presionar Guardar."
    )
    faq_box_3 = (
        "<b>¿Qué significa si una guía figura como 'No Entregada'?</b><br/>"
        "Son guías que en la propia hoja de reparto tenían una marca o anotación de 'NO' entrega. El sistema las reconoce "
        "y no te exigirá el remito físico firmado para poder archivar."
    )
    
    faq_table = Table([
        [Paragraph(faq_box_1, body_style)],
        [Paragraph(faq_box_2, body_style)],
        [Paragraph(faq_box_3, body_style)]
    ], colWidths=[522])
    
    faq_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f1f5f9")),
        ('BORDER', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(faq_table)
    story.append(Spacer(1, 8))

    # Support note
    support_table = Table([[
        Paragraph("<b>Soporte y Consultas:</b> Si encuentras algún inconveniente con el escáner o el sistema, comunícate con el administrador responsable del área.", callout_style)
    ]], colWidths=[522])
    support_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#fef3c7")),
        ('BORDER', (0,0), (-1,-1), 0.8, colors.HexColor("#fde68a")),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(support_table)

    # Build Document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF successfully generated at: {output_path}")

if __name__ == "__main__":
    out_file = Path(r"D:\GestorArchivo\Manual_de_Uso_GestorArchivo.pdf")
    generate_pdf(out_file)

# GestorArchivo - Gestor de Repartos y Digitalización

Este es un sistema diseñado para guardar, organizar, buscar y digitalizar hojas de reparto físicas digitalizadas en PDF. El sistema escanea una carpeta de **Entrada**, analiza los archivos PDF con texto embebido, identifica la *Hoja de Reparto*, extrae los metadatos relevantes (Empresa, Sucursal, Número de Reparto, Fecha), mueve la carpeta completa a una estructura ramificada organizada, y guarda la información en una base de datos PostgreSQL (con fallback a SQLite). Si falta información o hay algún error, la carpeta se mueve a **Revisión** para que el usuario ingrese los metadatos manualmente desde la interfaz gráfica.

## Estructura del Proyecto

```
d:/GestorArchivo/
│
├── app/                      # INTERFAZ (Streamlit)
│   ├── app.py                # Aplicación frontend de Streamlit
│   └── ui_components.py      # Componentes modulares de la interfaz
│
├── core/                     # LÓGICA PRINCIPAL
│   ├── ocr.py                # Módulo de extracción de texto (OCR / PyMuPDF)
│   └── organizer.py          # Orquestador del flujo de organización
│
├── services/                 # SERVICIOS (Infraestructura)
│   ├── db.py                 # Conexión a base de datos (PostgreSQL/SQLite)
│   ├── file_manager.py       # Utilidades para mover carpetas
│   └── pdf_reader.py         # Extracción de texto y metadatos con PyMuPDF
│
├── models/                   # MODELOS DE DATOS
│   └── database.py           # Modelos de tablas SQLAlchemy (Reparto)
│
├── config/                   # CONFIGURACIÓN GLOBAL
│   └── settings.py           # Parámetros globales y auto-creación de carpetas
│
├── launcher.py               # Ejecutor concurrente (Streamlit + FastAPI)
├── main.py                   # API Backend (FastAPI)
├── requirements.txt          # Dependencias
└── README.md                 # Documentación
```

## Requisitos e Instalación

1. **Python**: Se requiere Python 3.10 o superior.
2. **Dependencias**: Instalar las dependencias listadas en `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```
3. **Carpetas automáticas**: Al importar la configuración, se crearán de manera automática las siguientes carpetas en la raíz del proyecto si no existen:
   - `Entrada/` (Donde se colocan las subcarpetas a organizar)
   - `Salida/` (Donde se creará la ramificación organizada)
   - `Revision/` (Donde se moverán las carpetas que requieran intervención manual)

## Configuración de Base de Datos
Por defecto, la aplicación utiliza una base de datos SQLite local (`gestor_archivos.db`) creada en el directorio raíz.
Si deseas utilizar **PostgreSQL**, crea un archivo `.env` en la raíz del proyecto y define la variable `DATABASE_URL`:
```env
DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/nombre_db
```

## Ejecución del Proyecto

Puedes lanzar simultáneamente la interfaz de Streamlit (Frontend) y el servidor de FastAPI (Backend) ejecutando:
```bash
python launcher.py
```

- **Frontend (Streamlit)**: Accesible en `http://localhost:8501`
- **Backend (FastAPI)**: Accesible en `http://localhost:8000`
- **Documentación Interactiva (Swagger)**: Accesible en `http://localhost:8000/docs`

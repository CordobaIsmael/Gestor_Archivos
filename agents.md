# RESUMEN
Esta app es un gestor de archivos para guardar, organizar , encontrar y digitalizar archivos fisicos .
Se van a digitalizar archivos y se agruparan en una carpeta la cual va a ser reorganizada en una ramificacion de carpetas.
El objetivo es desde una carpeta encontrar el archivo indice a la que llamaremos *HOJA DE REPARTO* el cual va a contener Empresa, Fecha, Sucursal y numero de reparto y segun esos datos moverla a la ramificacion correspondiente.
Para encontrar estos metadatos, primero se escanearan los archivos, se escanean con OCR y se encuentran en la carpeta que especifiquemos, ya sea de ENTRADA o que elijamos.
Esto se procesa , y se reorganiza segun la informacion de la *HOJA DE REPARTO*, esta contiene *Empresa* (la cual solamente seran INTERPROVINCIAL y OTAPEYA), *Sucursal*, *Nro de reparto* y *Fecha*. Todos estos datos se guardaran en una Base de Datos.

# TECNOLOGIAS

En el frontend la UI se utilizara Streamlit
En el backend vamos a usar Python con las librerias FileSystem, Subprocess, PyMuPDF.
Como frameworks en el backend se usara FastAPI.
Como base de datos usaremos postgresql, y como ORM usaremos el ORM de FastAPI.

# ESTRUCTURA DEL PROYECTO

D:\GestorRepartos\
│
├── app\                      # INTERFAZ (Streamlit)
│   ├── app.py
│   └── ui_components.py
│
├── core\                     # LÓGICA PRINCIPAL
│
├── services\                 # SERVICIOS (infraestructura)
│   ├── db.py                 # PostgreSQL
│   ├── file_manager.py       # mover/copiar
│   ├── pdf_reader.py         # PyMuPDF
│
├── models\                   # MODELOS DE DATOS
│
├── config\                   # CONFIGURACIÓN GLOBAL
│   └── settings.py
│
├── launcher.py               # EXE
├── requirements.txt
├── README.md
└── .gitignore

## RESUMEN DE ESTRUCTURA

En la carpeta app se encontraria todo lo que sea relacionado a UI.
En la carpeta core se encontrara la logica de la app desde utilizar el OCR , la creacion de carpetas , mover y renombrar las carpetas, etc.
En la carpeta services se encontrara configuracion de la base de datos y servicios que seran utilizados por la logica de la app.

# FLUJO DE LA APP

Un usuario interactuara con la UI , en la cual podra ejecutar el script que organizara lo escaneado.
Recibira un feedback si el script fue ejecutado correctamente y si hubo carpetas que se tuvieron que mover a revision.
La app tendra la responsabilidad de leer de la carpeta *Entrada* en la cual habran subcarpetas que son las que el programa debera reorganizar.
La reorganizacion consiste en tomar una carpeta de la carpeta de *Entrada*, utilizar el OCR en todos los archivos dentro de la carpeta hasta encontrar el archivo principal que contiene los datos para organizar dicha carpeta. El archivo principal contendra los datos *Fecha*, *Sucursal*, *Empresa* y *Numero de reparto*. Con esta informacion sabremos donde rehubicar la carpeta procesada. Los datos del Archivo principal sera cargado en una base de datos para poder buscarlos segun sus datos.
Si al momento de reorganizar la carpeta hubo algun error, que esta carpeta se mueva a revision y el usuario resivira la notificacion. En la UI se mostrara las carpetas organizadas y las que fueron a revision. Si una carpeta fue a revision habra un desplegable en el cual se podra abrir dicha carpeta e ingresar los datos manualmente, y ejecutar la logica para organizar esa carpeta.
 

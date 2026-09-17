@echo off
chcp 65001 > nul
title GestorArchivo - Lanzador de Servidores
cd /d "%~dp0"

echo ==================================================
echo   Verificando paquetes necesarios...
echo ==================================================

python -c "import uvicorn, fastapi, streamlit, openpyxl, reportlab, fitz" >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Este usuario todavia no tiene los paquetes instalados.
    echo [*] Instalando dependencias de forma automatica (sin pedir permisos de Admin)...
    python -m pip install -r requirements.txt --user
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] No se pudieron instalar las dependencias automaticamente.
        echo Verifique su conexion a internet o ejecute: python -m pip install -r requirements.txt --user
        pause
        exit /b 1
    )
    echo [OK] Paquetes instalados con exito.
    echo.
)

echo ==================================================
echo   Iniciando GestorArchivo (Backend + Frontend)...
echo ==================================================
echo.
python launcher.py
echo.
echo ==================================================
echo   El servidor se ha detenido.
echo ==================================================
pause

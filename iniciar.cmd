@echo off
title GestorArchivo - Lanzador de Servidores
cd /d "%~dp0"
echo ==================================================
echo   Iniciando GestorArchivo (Backend + Frontend)...
echo ==================================================
echo.
python launcher.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Hubo un problema al iniciar la aplicacion.
    echo Asegurate de tener Python instalado y en el PATH.
    pause
)

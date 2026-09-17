@echo off
chcp 65001 > nul
title GestorArchivo - Lanzador de Servidores
cd /d "%~dp0"

echo ==================================================
echo   Iniciando GestorArchivo (Backend + Frontend)...
echo ==================================================
echo.

python launcher.py
if %errorlevel% neq 0 (
    echo.
    echo ================================================================
    echo [!] Es posible que falten paquetes en este usuario de Windows.
    echo [*] Instalando dependencias automaticamente (sin permisos de Admin)...
    echo ================================================================
    echo.
    python -m pip install -r requirements.txt --user
    echo.
    echo [*] Reintentando iniciar GestorArchivo...
    echo.
    python launcher.py
)

echo.
echo ==================================================
echo   El servidor se ha detenido.
echo ==================================================
pause

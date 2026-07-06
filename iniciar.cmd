@echo off
title GestorArchivo - Lanzador de Servidores
cd /d "%~dp0"
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

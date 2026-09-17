@echo off
chcp 65001 > nul
title GestorArchivo - Instalador de Dependencias
cd /d "%~dp0"

echo ================================================================
echo   Instalando dependencias de GestorArchivo para este usuario
echo   (No requiere permisos de Administrador)
echo ================================================================
echo.

python -m pip install -r requirements.txt --user

echo.
echo ================================================================
echo   Instalacion finalizada. Ya puedes ejecutar iniciar.cmd
echo ================================================================
pause

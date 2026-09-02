@echo off
chcp 65001 > nul
echo ==================================================
echo -> Deteniendo GestorArchivo (Backend y Frontend)...
echo ==================================================

powershell -Command "Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess -Force -ErrorAction SilentlyContinue; Stop-Process -Id (Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue).OwningProcess -Force -ErrorAction SilentlyContinue"

echo [OK] Procesos detenidos correctamente.
timeout /t 2 > nul

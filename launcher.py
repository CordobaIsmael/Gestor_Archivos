import subprocess
import sys
import time
import os
import signal
from pathlib import Path

def launch():
    print("==================================================")
    print("-> Iniciando GestorArchivo (Backend + Frontend)...")
    print("==================================================")

    # Base workspace directory
    base_dir = Path(__file__).resolve().parent
    
    # 1. Start FastAPI Backend (Uvicorn)
    backend_cmd = [
        sys.executable, "-m", "uvicorn", "main:app",
        "--host", "127.0.0.1",
        "--port", "8000"
    ]
    print("-> Iniciando Backend (FastAPI) en http://127.0.0.1:8000...")
    backend_proc = subprocess.Popen(
        backend_cmd, 
        cwd=str(base_dir)
    )
    
    # Wait briefly to let the database initialize and backend start
    time.sleep(2)
    
    # Check if backend started successfully
    if backend_proc.poll() is not None:
        print("[ERROR] Error al iniciar el Backend (FastAPI).")
        sys.exit(1)

    # 2. Start Streamlit Frontend
    frontend_cmd = [
        sys.executable, "-m", "streamlit", "run", "app/app.py"
    ]
    print("-> Iniciando Frontend (Streamlit) en http://127.0.0.1:8501...")
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=str(base_dir)
    )

    print("\n==================================================")
    print("[OK] Aplicacion corriendo con exito!")
    print("   - API Backend: http://127.0.0.1:8000")
    print("   - Swagger Docs: http://127.0.0.1:8000/docs")
    print("   - Frontend Streamlit: http://127.0.0.1:8501")
    print("Presiona Ctrl+C para detener ambos procesos.")
    print("==================================================\n")

    # Keep launcher running and monitor processes
    try:
        while True:
            # Check if backend or frontend died
            if backend_proc.poll() is not None:
                print("[WARNING] El servidor Backend se ha detenido inesperadamente.")
                break
            if frontend_proc.poll() is not None:
                print("[WARNING] La aplicacion Frontend se ha detenido inesperadamente.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDeteniendo procesos...")
    finally:
        # Clean shutdown of both processes
        print("Cerrando Backend...")
        try:
            backend_proc.terminate()
            backend_proc.wait(timeout=3)
        except Exception:
            backend_proc.kill()
            
        print("Cerrando Frontend...")
        try:
            frontend_proc.terminate()
            frontend_proc.wait(timeout=3)
        except Exception:
            frontend_proc.kill()
            
        print("[OK] ¡Hasta luego!")

if __name__ == "__main__":
    launch()

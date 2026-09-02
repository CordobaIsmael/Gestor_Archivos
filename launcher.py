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
    
    import socket
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "localhost"

    local_ip = get_local_ip()

    # 1. Start FastAPI Backend (Uvicorn)
    backend_cmd = [
        sys.executable, "-m", "uvicorn", "main:app",
        "--host", "0.0.0.0",
        "--port", "8000"
    ]
    print("-> Iniciando Backend (FastAPI) en http://0.0.0.0:8000...")
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

    # 2. Start Streamlit Frontend (headless so it binds to 0.0.0.0 for LAN access without opening invalid 0.0.0.0 in browser)
    frontend_cmd = [
        sys.executable, "-m", "streamlit", "run", "app/app.py",
        "--server.address", "0.0.0.0",
        "--server.port", "8501",
        "--server.headless", "true"
    ]
    print("-> Iniciando Frontend (Streamlit) en http://0.0.0.0:8501...")
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=str(base_dir)
    )

    # Automatically open the correct localhost URL in the user's browser
    import webbrowser
    time.sleep(2)
    try:
        webbrowser.open("http://localhost:8501")
    except Exception:
        pass

    print("\n==================================================")
    print("[OK] ¡Aplicación corriendo con éxito!")
    print(f"   - Acceso Local (esta PC): http://localhost:8501")
    if local_ip != "localhost":
        print(f"   - Acceso en Red Local (otras PC): http://{local_ip}:8501")
    print(f"   - API Backend: http://localhost:8000")
    print(f"   - Swagger Docs: http://localhost:8000/docs")
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

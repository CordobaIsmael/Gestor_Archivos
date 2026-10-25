import os
import socket
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

def get_local_ip() -> str:
    """Detects the LAN IP of the current host machine for multi-PC network access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

def is_network_server_available(ip: str = "192.168.0.99", port: int = 445, timeout: float = 0.8) -> bool:
    """Fast check to verify if the central storage server is online and reachable on the LAN."""
    try:
        s = socket.create_connection((ip, port), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False

class Settings(BaseSettings):
    # Base workspace directory (defaulting to parent of config/ folder)
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    # File organization paths (local staging)
    ENTRADA: Path = BASE_DIR / "Entrada"
    SALIDA: Path = BASE_DIR / "Salida"
    REVISION: Path = BASE_DIR / "Revision"

    # Central storage server IP for network terminals
    STORAGE_SERVER_IP: str = "192.168.0.99"

    # Company specific target paths for network terminals (Rutas de red UNC)
    DIR_INTERPROVINCIAL: Path = Path(r"\\192.168.0.99\ad_interprovincial_red")
    DIR_OTAPEYA: Path = Path(r"\\192.168.0.99\ad_otapeya_red")

    # Company specific mirror paths (Read-only query storage)
    MIRROR_DIR_INTERPROVINCIAL: Path = Path("Q:/")
    MIRROR_DIR_OTAPEYA: Path = Path("O:/")

    # Database settings (Ruta de red compartida para terminales)
    DIR_BASE_DATOS: Path = Path(r"\\192.168.0.99\base_gestor_archivos")
    DATABASE_FILE: Path = Path(r"\\192.168.0.99\base_gestor_archivos\gestor_archivos.db")
    DATABASE_URL: str = "sqlite://///192.168.0.99/base_gestor_archivos/gestor_archivos.db"

    # Server & API configuration for LAN access
    SERVER_IP: str = get_local_ip()
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8502
    API_URL: str = f"http://{get_local_ip()}:8502"


    # Official valid sucursales
    VALID_SUCURSALES: dict = {
        "MP": "Mar del Plata",
        "TA": "Tres Arroyos",
        "CO": "Córdoba",
        "OL": "Olavarría",
        "VR": "Villa Regina",
        "RC": "Río Colorado",
        "CH": "Choele Choel",
        "BB": "Bahía Blanca",
        "CF": "Capital Federal",
        "NQ": "Neuquén",
        "RO": "Rosario",
        "AZ": "Azul",
        "TD": "Tandil",
        "GR": "General Roca"
    }

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def create_directories(self):
        """Creates the necessary directories if they do not exist."""
        for path in [self.ENTRADA, self.SALIDA, self.REVISION]:
            try:
                path.mkdir(parents=True, exist_ok=True)
                print(f"Directory verified/created: {path}")
            except Exception as e:
                print(f"Could not create directory {path}: {e}")

        # Check if storage server is reachable before probing network shares
        if is_network_server_available(self.STORAGE_SERVER_IP):
            for path in [self.DIR_INTERPROVINCIAL, self.DIR_OTAPEYA, self.DIR_BASE_DATOS]:
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    print(f"Network directory verified/created: {path}")
                except Exception as e:
                    print(f"Note: Network share {path} not directly accessible: {e}")

            # If DIR_BASE_DATOS exists and database file is missing, copy existing database over
            try:
                if self.DIR_BASE_DATOS.exists():
                    target_db = self.DATABASE_FILE
                    local_db = self.BASE_DIR / "gestor_archivos.db"
                    if not target_db.exists() and local_db.exists():
                        import shutil
                        shutil.copy2(local_db, target_db)
                        print(f"Database migrated successfully to: {target_db}")
            except Exception as e:
                print(f"Note: Could not verify/copy initial database to {self.DIR_BASE_DATOS}: {e}")
        else:
            print(f"Note: Storage server {self.STORAGE_SERVER_IP} is not reachable on this network. Network shares not connected.")

# Instantiate global settings
settings = Settings()
# Ensure directories are created on import
settings.create_directories()

# Minimum digits required for nro_reparto per sucursal
MIN_DIGITS_BY_SUCURSAL: dict = {
    "BB": 6,
    "CF": 5,
    "NQ": 5,
    "TD": 4,
    "VR": 4,
    "OL": 4,
    "GR": 4,
    "TA": 4,
}
DEFAULT_MIN_DIGITS: int = 3

def get_min_digits_for_sucursal(sucursal: str) -> int:
    """Returns the minimum number of digits required for a sucursal's nro_reparto."""
    if not sucursal:
        return DEFAULT_MIN_DIGITS
    suc_code = str(sucursal).upper().strip()
    return MIN_DIGITS_BY_SUCURSAL.get(suc_code, DEFAULT_MIN_DIGITS)

def validate_nro_reparto_digits(sucursal: str, nro_reparto: str) -> tuple:
    """
    Validates that nro_reparto contains at least the required minimum numeric digits for the given sucursal.
    Returns: (is_valid: bool, actual_digits: int, required_min_digits: int)
    """
    req_min = get_min_digits_for_sucursal(sucursal)
    if not nro_reparto:
        return False, 0, req_min
    import re
    digits = re.sub(r"\D", "", str(nro_reparto))
    return len(digits) >= req_min, len(digits), req_min

# Path persistence utilities
import json
CONFIG_FILE = settings.BASE_DIR / "user_config.json"

def get_persisted_paths() -> dict:
    """Loads saved input directory paths from user_config.json."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print(f"Error reading user_config.json: {e}")
    return {
        "scan_path": str(Path(settings.ENTRADA).resolve()),
        "salida_path": ""
    }

def save_persisted_paths(scan_path: str = None, salida_path: str = None):
    """Saves directory paths to user_config.json to persist across sessions."""
    data = get_persisted_paths()
    if scan_path is not None and scan_path.strip():
        data["scan_path"] = str(Path(scan_path).resolve())
    if salida_path is not None:
        data["salida_path"] = str(Path(salida_path).resolve()) if salida_path.strip() else ""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving user_config.json: {e}")

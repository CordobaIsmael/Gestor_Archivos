import os
import socket
import json
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Official valid sucursales segregated by company
SUCURSALES_OTAPEYA: dict = {
    "CC": "Casa Central (Bahía Blanca)",
    "BA": "Capital Federal (Buenos Aires)",
    "NQ": "Neuquén"
}

SUCURSALES_INTERPROVINCIAL: dict = {
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

def get_valid_sucursales(empresa: str = None) -> dict:
    """Returns official sucursales dictionary for the given empresa."""
    emp = (empresa or "").upper().strip()
    if emp == "OTAPEYA":
        return SUCURSALES_OTAPEYA
    elif emp == "INTERPROVINCIAL":
        return SUCURSALES_INTERPROVINCIAL
    return {**SUCURSALES_INTERPROVINCIAL, **SUCURSALES_OTAPEYA}

def is_valid_sucursal_for_empresa(empresa: str, sucursal: str) -> bool:
    """Checks whether the sucursal code is valid for the specific empresa."""
    if not sucursal:
        return False
    suc = str(sucursal).upper().strip()
    valid_map = get_valid_sucursales(empresa)
    return suc in valid_map

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

def get_configured_storage_mode(base_dir: Path, server_ip: str = "192.168.0.99") -> str:
    r"""
    Determines storage mode: 'local' (server with physical drive A:\) or 'network' (UNC terminal).
    Priority:
    1. user_config.json ('storage_mode': 'local' | 'network')
    2. Environment variable STORAGE_MODE ('local' | 'network')
    3. Auto-detection:
       - If physical drive A:\ exists -> 'local'
       - If local IP matches server_ip -> 'local'
       - Otherwise -> 'network'
    """
    # 1. user_config.json
    cfg_file = base_dir / "user_config.json"
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                m = str(data.get("storage_mode", "")).strip().lower()
                if m in ["local", "network"]:
                    return m
        except Exception:
            pass

    # 2. Environment variable
    env_m = os.getenv("STORAGE_MODE", "").strip().lower()
    if env_m in ["local", "network"]:
        return env_m

    # 3. Auto-detection
    try:
        if Path("A:/").exists():
            return "local"
    except Exception:
        pass

    try:
        if get_local_ip() == server_ip:
            return "local"
    except Exception:
        pass

    return "network"

class Settings(BaseSettings):
    # Base workspace directory (defaulting to parent of config/ folder)
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    # File organization paths (local staging)
    ENTRADA: Path = BASE_DIR / "Entrada"
    SALIDA: Path = BASE_DIR / "Salida"
    REVISION: Path = BASE_DIR / "Revision"

    # Central storage server IP for network terminals
    STORAGE_SERVER_IP: str = "192.168.0.99"

    # Company specific mirror paths (Read-only query storage)
    MIRROR_DIR_INTERPROVINCIAL: Path = Path("Q:/")
    MIRROR_DIR_OTAPEYA: Path = Path("O:/")

    # Dynamic storage mode and target paths
    STORAGE_MODE: str = "auto"
    IS_LOCAL_SERVER: bool = False

    DIR_INTERPROVINCIAL: Path = Path(r"A:\AD_INTERPROVINCIAL")
    DIR_OTAPEYA: Path = Path(r"A:\AD_OTAPEYA")
    DIR_BASE_DATOS: Path = Path(r"A:\BASE_GESTOR_ARCHIVOS")
    DATABASE_FILE: Path = Path(r"A:\BASE_GESTOR_ARCHIVOS\gestor_archivos.db")
    DATABASE_URL: str = "sqlite:///A:/BASE_GESTOR_ARCHIVOS/gestor_archivos.db"

    # Server & API configuration for LAN access
    SERVER_IP: str = get_local_ip()
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8502
    API_URL: str = f"http://{get_local_ip()}:8502"

    # Combined valid sucursales dictionary for global lookup
    VALID_SUCURSALES: dict = {
        **SUCURSALES_INTERPROVINCIAL,
        **SUCURSALES_OTAPEYA
    }

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def apply_storage_mode(self, mode: str = None):
        r"""
        Configures paths according to storage mode:
        - 'local': Uses physical drive A:\ (A:\AD_INTERPROVINCIAL, A:\AD_OTAPEYA, A:\BASE_GESTOR_ARCHIVOS)
        - 'network': Uses UNC network shares (\\192.168.0.99\ad_interprovincial_red, etc.)
        """
        if not mode or mode == "auto":
            mode = get_configured_storage_mode(self.BASE_DIR, self.STORAGE_SERVER_IP)
        self.STORAGE_MODE = mode
        self.IS_LOCAL_SERVER = (mode == "local")

        if self.IS_LOCAL_SERVER:
            self.DIR_INTERPROVINCIAL = Path(r"A:\AD_INTERPROVINCIAL")
            self.DIR_OTAPEYA = Path(r"A:\AD_OTAPEYA")
            self.DIR_BASE_DATOS = Path(r"A:\BASE_GESTOR_ARCHIVOS")
            self.DATABASE_FILE = Path(r"A:\BASE_GESTOR_ARCHIVOS\gestor_archivos.db")
            self.DATABASE_URL = "sqlite:///A:/BASE_GESTOR_ARCHIVOS/gestor_archivos.db"
        else:
            self.DIR_INTERPROVINCIAL = Path(rf"\\{self.STORAGE_SERVER_IP}\ad_interprovincial_red")
            self.DIR_OTAPEYA = Path(rf"\\{self.STORAGE_SERVER_IP}\ad_otapeya_red")
            self.DIR_BASE_DATOS = Path(rf"\\{self.STORAGE_SERVER_IP}\base_gestor_archivos")
            self.DATABASE_FILE = Path(rf"\\{self.STORAGE_SERVER_IP}\base_gestor_archivos\gestor_archivos.db")
            self.DATABASE_URL = f"sqlite://///{self.STORAGE_SERVER_IP}/base_gestor_archivos/gestor_archivos.db"

    def create_directories(self):
        """Creates the necessary directories if they do not exist."""
        for path in [self.ENTRADA, self.SALIDA, self.REVISION]:
            try:
                path.mkdir(parents=True, exist_ok=True)
                print(f"Directory verified/created: {path}")
            except Exception as e:
                print(f"Could not create directory {path}: {e}")

        if self.IS_LOCAL_SERVER:
            # Local Server: check if drive A: exists
            try:
                has_a_drive = Path("A:/").exists()
            except Exception:
                has_a_drive = False

            if has_a_drive:
                for path in [self.DIR_INTERPROVINCIAL, self.DIR_OTAPEYA, self.DIR_BASE_DATOS]:
                    try:
                        path.mkdir(parents=True, exist_ok=True)
                        print(f"Local storage directory verified/created: {path}")
                    except Exception as e:
                        print(f"Note: Local drive A: path {path} not accessible: {e}")

                # Copy existing local workspace database to A:\BASE_GESTOR_ARCHIVOS if not present
                try:
                    if self.DIR_BASE_DATOS.exists():
                        target_db = self.DATABASE_FILE
                        local_db = self.BASE_DIR / "gestor_archivos.db"
                        if not target_db.exists() and local_db.exists():
                            import shutil
                            shutil.copy2(local_db, target_db)
                            print(f"Database migrated successfully to local server storage: {target_db}")
                except Exception as e:
                    print(f"Note: Could not copy initial database to {self.DIR_BASE_DATOS}: {e}")
            else:
                print("Note: Local server mode active, but drive A: is not mounted.")
        else:
            # Network Terminal: Check if storage server is reachable before probing network shares
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

# Instantiate global settings and apply storage mode
settings = Settings()
settings.apply_storage_mode()
# Ensure directories are created on import
settings.create_directories()

# Minimum digits required for nro_reparto per sucursal (Interprovincial only)
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

def get_min_digits_for_sucursal(sucursal: str, empresa: str = None) -> int:
    """
    Returns minimum required digits for a sucursal's nro_reparto.
    Otapeya (CC, BA, NQ) uses smaller numbers and is EXEMPT from minimum digit constraints.
    """
    emp = (empresa or "").upper().strip()
    suc_code = str(sucursal).upper().strip() if sucursal else ""
    if emp == "OTAPEYA" or suc_code in ["CC", "BA"]:
        return 1
    return MIN_DIGITS_BY_SUCURSAL.get(suc_code, DEFAULT_MIN_DIGITS)

def validate_nro_reparto_digits(sucursal: str, nro_reparto: str, empresa: str = None) -> tuple:
    """
    Validates that nro_reparto contains at least the required minimum numeric digits.
    Otapeya (CC, BA, NQ) has smaller numbers and is EXEMPT from minimum digit requirements (any 1+ digits valid).
    Returns: (is_valid: bool, actual_digits: int, required_min_digits: int)
    """
    if not nro_reparto:
        return False, 0, 1
    import re
    digits = re.sub(r"\D", "", str(nro_reparto))
    act_digits = len(digits)
    if act_digits == 0:
        return False, 0, 1

    emp = (empresa or "").upper().strip()
    suc_code = str(sucursal).upper().strip() if sucursal else ""

    # Otapeya has smaller numbering: exempt from minimum digits check
    if emp == "OTAPEYA" or suc_code in ["CC", "BA"]:
        return True, act_digits, 1

    req_min = get_min_digits_for_sucursal(suc_code, empresa=emp)
    return act_digits >= req_min, act_digits, req_min

# Path and configuration persistence utilities
CONFIG_FILE = settings.BASE_DIR / "user_config.json"

def get_persisted_paths() -> dict:
    """Loads saved input directory paths and storage mode from user_config.json."""
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
        "salida_path": "",
        "storage_mode": "auto"
    }

def save_persisted_paths(scan_path: str = None, salida_path: str = None, storage_mode: str = None):
    """Saves directory paths and storage mode to user_config.json to persist across sessions."""
    data = get_persisted_paths()
    if scan_path is not None and scan_path.strip():
        data["scan_path"] = str(Path(scan_path).resolve())
    if salida_path is not None:
        data["salida_path"] = str(Path(salida_path).resolve()) if salida_path.strip() else ""
    if storage_mode is not None and storage_mode.strip():
        data["storage_mode"] = storage_mode.strip().lower()
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving user_config.json: {e}")

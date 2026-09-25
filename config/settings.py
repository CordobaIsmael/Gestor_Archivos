import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Base workspace directory (defaulting to parent of config/ folder)
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    # File organization paths
    ENTRADA: Path = BASE_DIR / "Entrada"
    SALIDA: Path = BASE_DIR / "Salida"
    REVISION: Path = BASE_DIR / "Revision"

    # Company specific target paths (Original master storage)
    DIR_INTERPROVINCIAL: Path = Path(r"A:\AD_INTERPROVINCIAL")
    DIR_OTAPEYA: Path = Path(r"A:\AD_OTAPEYA")

    # Company specific mirror paths (Read-only query storage)
    MIRROR_DIR_INTERPROVINCIAL: Path = Path(r"Q:\AD_INTERPROVINCIAL")
    MIRROR_DIR_OTAPEYA: Path = Path(r"O:\AD_OTAPEYA")

    # Database settings
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/gestor_archivos.db"

    # API configuration
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    API_URL: str = "http://127.0.0.1:8000"

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
        "AZ": "Azul"
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

        for path in [self.DIR_INTERPROVINCIAL, self.DIR_OTAPEYA]:
            try:
                path.mkdir(parents=True, exist_ok=True)
                print(f"Directory verified/created: {path}")
            except Exception as e:
                print(f"Note: Drive/directory {path} not directly accessible yet: {e}")

# Instantiate global settings
settings = Settings()
# Ensure directories are created on import
settings.create_directories()

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

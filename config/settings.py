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

    # Database settings
    # Defaulting to local SQLite file for development.
    # Production will set DATABASE_URL to a PostgreSQL connection string (e.g. postgresql://user:password@localhost:5432/db_name)
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/gestor_archivos.db"

    # API configuration
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    API_URL: str = "http://127.0.0.1:8000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def create_directories(self):
        """Creates the necessary directories if they do not exist."""
        for path in [self.ENTRADA, self.SALIDA, self.REVISION]:
            path.mkdir(parents=True, exist_ok=True)
            print(f"Directory verified/created: {path}")

# Instantiate global settings
settings = Settings()
# Ensure directories are created on import
settings.create_directories()

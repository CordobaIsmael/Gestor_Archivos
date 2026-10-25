from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config.settings import settings, is_network_server_available
from models.database import Base
from pathlib import Path

# Determine effective DATABASE_URL
db_url = settings.DATABASE_URL
if settings.STORAGE_SERVER_IP in db_url:
    # If central storage server is offline on this network, fallback to local workspace database
    if not is_network_server_available(settings.STORAGE_SERVER_IP):
        fallback_path = settings.BASE_DIR / "gestor_archivos.db"
        print(f"Note: Storage server {settings.STORAGE_SERVER_IP} is offline. Using local database: {fallback_path}")
        db_url = f"sqlite:///{fallback_path.as_posix()}"
elif db_url.startswith("sqlite:///"):
    db_file_str = db_url.replace("sqlite:///", "")
    target_path = Path(db_file_str)
    # If target is on a Windows drive that is not mounted on this PC, fallback to local workspace
    if target_path.drive and not Path(f"{target_path.drive}/").exists():
        fallback_path = settings.BASE_DIR / "gestor_archivos.db"
        print(f"Note: Target database drive {target_path.drive} is not mounted. Using local database: {fallback_path}")
        db_url = f"sqlite:///{fallback_path.as_posix()}"

# Determine connect_args based on DB type (SQLite needs check_same_thread=False and timeout for network drives)
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    connect_args["timeout"] = 30

engine = create_engine(
    db_url,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Create all tables in the database."""
    from sqlalchemy import text
    Base.metadata.create_all(bind=engine)
    
    # Try adding columns to existing repartos table (schema migrations)
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE repartos ADD COLUMN guias_encontradas VARCHAR(2000)"))
            print("Added guias_encontradas column (migration).")
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE repartos ADD COLUMN guias_faltantes VARCHAR(2000)"))
            print("Added guias_faltantes column (migration).")
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE repartos ADD COLUMN guias_no_entregadas VARCHAR(2000)"))
            print("Added guias_no_entregadas column (migration).")
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE repartos ADD COLUMN resolucion_guias_faltantes VARCHAR(4000)"))
            print("Added resolucion_guias_faltantes column (migration).")
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE repartos ADD COLUMN guias_sin_firma VARCHAR(2000)"))
            print("Added guias_sin_firma column (migration).")
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE repartos ADD COLUMN usuario_id INTEGER"))
            print("Added usuario_id column to repartos (migration).")
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE repartos ADD COLUMN usuario_legajo VARCHAR(50)"))
            print("Added usuario_legajo column to repartos (migration).")
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE repartos ADD COLUMN es_duplicado BOOLEAN DEFAULT 0"))
            print("Added es_duplicado column to repartos (migration).")
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE repartos ADD COLUMN motivo_revision VARCHAR(500)"))
            print("Added motivo_revision column to repartos (migration).")
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE repartos ADD COLUMN ruta_espejo VARCHAR(500)"))
            print("Added ruta_espejo column to repartos (migration).")
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE repartos ADD COLUMN fecha_anulacion DATETIME"))
            print("Added fecha_anulacion column to repartos (migration).")
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE repartos ADD COLUMN usuario_anulacion VARCHAR(50)"))
            print("Added usuario_anulacion column to repartos (migration).")
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE repartos ADD COLUMN motivo_anulacion VARCHAR(500)"))
            print("Added motivo_anulacion column to repartos (migration).")
    except Exception:
        pass

    # Bootstrap default admin user 1101 if not exists
    from models.database import Usuario
    import hashlib
    with SessionLocal() as db_session:
        admin_user = db_session.query(Usuario).filter(Usuario.legajo == "1101").first()
        if not admin_user:
            # Default password for 1101 is '1101'
            pwd_hash = hashlib.sha256("1101".encode('utf-8')).hexdigest()
            admin_user = Usuario(
                legajo="1101",
                nombre="Administrador",
                password_hash=pwd_hash,
                rol="ADMIN",
                activo=True
            )
            db_session.add(admin_user)
            db_session.commit()
            print("Bootstrap: Initial admin user (1101) created successfully.")
        
    print("Database tables initialized successfully.")

def get_db():
    """Database session generator (dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

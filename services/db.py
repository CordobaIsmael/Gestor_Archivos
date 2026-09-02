from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config.settings import settings
from models.database import Base

# Determine connect_args based on DB type (SQLite needs check_same_thread=False)
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
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
            conn.execute(text("ALTER TABLE repartos ADD COLUMN caja_id INTEGER"))
            print("Added caja_id column to repartos table (migration).")
    except Exception:
        pass
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
            conn.execute(text("ALTER TABLE repartos ADD COLUMN resolucion_guias_sin_firma VARCHAR(4000)"))
            print("Added resolucion_guias_sin_firma column (migration).")
    except Exception:
        pass
        
    print("Database tables initialized successfully.")

def get_db():
    """Database session generator (dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

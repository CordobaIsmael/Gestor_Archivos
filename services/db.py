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
    
    # Try adding caja_id column to existing repartos table (schema migration)
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE repartos ADD COLUMN caja_id INTEGER"))
            print("Added caja_id column to repartos table (migration).")
    except Exception:
        # Ignore if column already exists
        pass
        
    print("Database tables initialized successfully.")

def get_db():
    """Database session generator (dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

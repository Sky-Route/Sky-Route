"""Conexión a la base de datos con SQLAlchemy. La usan solo los repositorios."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Clase base de las tablas (modelos ORM) de todos los módulos."""


def get_db():
    """Entrega una sesión por petición y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def database_is_up() -> bool:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True

from contextlib import contextmanager

from sqlmodel import Session, create_engine

from config import settings

# Crear el engine de la base de datos
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,  # Muestra SQL queries en desarrollo
    pool_pre_ping=True,  # Verifica conexiones antes de usar
)


def get_session():
    """
    Dependency para obtener una sesión de base de datos.
    Usar en FastAPI con Depends(get_session).
    """
    with Session(engine) as session:
        yield session


@contextmanager
def get_db_session():
    """Context manager para usar fuera de FastAPI"""
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

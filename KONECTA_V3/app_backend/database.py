"""SQLAlchemy engine e sessão.

Suporta SQLite (dev) e PostgreSQL (prod). SQLite usa WAL para melhor
concorrência e backups online.
"""

from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app_backend.config import settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


class Base(DeclarativeBase):
    """Base declarativa compartilhada por todos os modelos ORM."""


def _build_engine() -> Engine:
    url = settings.database_url
    kwargs: dict = {"echo": settings.db_echo, "future": True}

    if url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        sqlite_path = settings.sqlite_path
        if sqlite_path is not None:
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
    else:
        kwargs["pool_size"] = settings.db_pool_size
        kwargs["max_overflow"] = settings.db_max_overflow
        kwargs["pool_pre_ping"] = settings.db_pool_pre_ping

    return create_engine(url, **kwargs)


def _enable_sqlite_wal(engine: Engine) -> None:
    """Ativa WAL e pragmas úteis no SQLite."""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def get_engine() -> Engine:
    """Retorna o engine (cacheado)."""
    global _engine
    if _engine is None:
        _engine = _build_engine()
        if settings.database_url.startswith("sqlite"):
            _enable_sqlite_wal(_engine)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), class_=Session, autocommit=False, autoflush=False
        )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Dependência FastAPI: sessão por request."""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def check_db_connectivity() -> bool:
    """Verifica se o banco responde a um SELECT 1."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def init_db() -> None:
    """Cria tabelas se não existirem (bootstrap de dev/testes).

    Em produção use Alembic: `alembic upgrade head`.
    """
    import app_backend.models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())

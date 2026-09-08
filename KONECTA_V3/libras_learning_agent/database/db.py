"""Engine, sessão e bootstrap do banco do LLA.

Independente do `app_backend`: `Base` própria, engine próprio. Nada daqui é
importado de/para `app_backend`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from libras_learning_agent.core.config import Settings, get_settings


class Base(DeclarativeBase):
    """Base declarativa do Libras Learning Agent."""


def _sqlite_path(database_url: str) -> Optional[Path]:
    prefix = "sqlite:///"
    if database_url.startswith(prefix):
        return Path(database_url[len(prefix) :])
    return None


def get_engine(settings: Optional[Settings] = None) -> Engine:
    """Cria um engine a partir de `settings.database_url`.

    Sem cache de módulo de propósito: cada chamada com `settings` diferentes
    (ex. em teste, apontando para um SQLite temporário) recebe um engine
    coerente com aquele `settings`, sem contaminação entre testes.
    """
    settings = settings or get_settings()
    url = settings.database_url
    kwargs: dict = {"future": True}

    sqlite_path = _sqlite_path(url)
    if sqlite_path is not None:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}

    return create_engine(url, **kwargs)


def get_session_factory(settings: Optional[Settings] = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(settings), class_=Session, autocommit=False, autoflush=False)


def get_db(settings: Optional[Settings] = None) -> Generator[Session, None, None]:
    """Sessão por uso (`with` ou injeção de dependência)."""
    session = get_session_factory(settings)()
    try:
        yield session
    finally:
        session.close()


def init_db(settings: Optional[Settings] = None) -> None:
    """Cria `data_dir` e as tabelas via `Base.metadata.create_all` (bootstrap rápido).

    Em uso real prefira Alembic: `database/migrations/`.
    """
    settings = settings or get_settings()
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)

    import libras_learning_agent.database.models  # noqa: F401 — registra os modelos em Base.metadata

    Base.metadata.create_all(bind=get_engine(settings))

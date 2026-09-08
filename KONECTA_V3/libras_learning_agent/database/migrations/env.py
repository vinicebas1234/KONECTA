"""Ambiente do Alembic do Libras Learning Agent (independente do app_backend).

Lê a URL do banco de `Settings` (env var `LLA_DATABASE_URL` / `.env`), no
mesmo padrão que `app_backend/migrations/env.py` usa como referência.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# env.py está em libras_learning_agent/database/migrations/env.py;
# parents[3] é a raiz do KONECTA_V3 (onde libras_learning_agent é um pacote).
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from libras_learning_agent.core.config import get_settings  # noqa: E402
from libras_learning_agent.database.db import Base  # noqa: E402
import libras_learning_agent.database.models  # noqa: E402, F401 — registra os modelos

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
# Sobrescreve a URL do .ini com a de Settings (.env / variáveis de ambiente)
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite") if url else False,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    url = settings.database_url
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=url.startswith("sqlite"),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

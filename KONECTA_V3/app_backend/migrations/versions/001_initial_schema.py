"""Initial schema: users, signals, ml_models

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-08-11
"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("api_key_hash", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_api_key_hash", "users", ["api_key_hash"])

    op.create_table(
        "ml_models",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=True),
        sa.Column(
            "is_available", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_ml_models_name_version"),
    )
    op.create_index("ix_ml_models_name", "ml_models", ["name"])
    op.create_index("ix_ml_models_is_available", "ml_models", ["is_available"])

    op.create_table(
        "signals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("signal_label", sa.String(length=128), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("model_used", sa.String(length=128), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_signals_user_id"
        ),
    )
    op.create_index("ix_signals_user_id", "signals", ["user_id"])
    op.create_index("ix_signals_created_at", "signals", ["created_at"])
    op.create_index("ix_signals_signal_label", "signals", ["signal_label"])
    op.create_index("ix_signals_user_created", "signals", ["user_id", "created_at"])

    # Seed: modelo padrão konecta_v3 v1
    now = datetime(2026, 8, 11, 0, 0, 0)
    op.execute(
        sa.text(
            """
            INSERT INTO ml_models
              (id, name, version, path, is_available, accuracy, metadata_json, created_at, updated_at)
            VALUES
              (
                '00000000-0000-4000-8000-000000000001',
                'konecta_v3',
                '1',
                'models/konecta_v3',
                1,
                NULL,
                '{"seeded": true, "description": "Modelo padrao KONECTA V3"}',
                :created_at,
                :updated_at
              )
            """
        ).bindparams(created_at=now, updated_at=now)
    )


def downgrade() -> None:
    op.drop_index("ix_signals_user_created", table_name="signals")
    op.drop_index("ix_signals_signal_label", table_name="signals")
    op.drop_index("ix_signals_created_at", table_name="signals")
    op.drop_index("ix_signals_user_id", table_name="signals")
    op.drop_table("signals")

    op.drop_index("ix_ml_models_is_available", table_name="ml_models")
    op.drop_index("ix_ml_models_name", table_name="ml_models")
    op.drop_table("ml_models")

    op.drop_index("ix_users_api_key_hash", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")

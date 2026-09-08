"""Add signal_sources: vínculo Signal<->Source (Ciclo 5)

Revision ID: 0002_add_signal_sources
Revises: 0001_initial_schema
Create Date: 2026-09-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_signal_sources"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signal_sources",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("signal_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["signal_id"], ["signals.id"], ondelete="CASCADE", name="fk_signal_sources_signal_id"
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="CASCADE", name="fk_signal_sources_source_id"
        ),
        sa.UniqueConstraint("signal_id", "source_id", name="uq_signal_sources_signal_id_source_id"),
    )
    op.create_index("ix_signal_sources_signal_id", "signal_sources", ["signal_id"])
    op.create_index("ix_signal_sources_source_id", "signal_sources", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_signal_sources_source_id", table_name="signal_sources")
    op.drop_index("ix_signal_sources_signal_id", table_name="signal_sources")
    op.drop_table("signal_sources")

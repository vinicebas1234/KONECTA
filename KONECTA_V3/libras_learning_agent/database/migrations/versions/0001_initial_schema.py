"""Initial schema: sources, videos, signals, signal_variants, landmark_samples,
validations, training_runs, model_versions, agent_tasks, agent_events

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("license", sa.String(length=128), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reliability_score", sa.Float(), nullable=True),
        sa.Column("usage_notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_sources_source_type", "sources", ["source_type"])

    op.create_table(
        "videos",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("url_or_path", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("fps", sa.Float(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("license", sa.String(length=128), nullable=True),
        sa.Column("processing_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="SET NULL", name="fk_videos_source_id"
        ),
    )
    op.create_index("ix_videos_source_id", "videos", ["source_id"])
    op.create_index("ix_videos_processing_status", "videos", ["processing_status"])

    op.create_table(
        "signals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("concept", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DISCOVERED"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_signals_concept", "signals", ["concept"])
    op.create_index("ix_signals_status", "signals", ["status"])

    op.create_table(
        "signal_variants",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("signal_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("region", sa.String(length=128), nullable=True),
        sa.Column("context", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(
            ["signal_id"], ["signals.id"], ondelete="CASCADE", name="fk_signal_variants_signal_id"
        ),
    )
    op.create_index("ix_signal_variants_signal_id", "signal_variants", ["signal_id"])

    op.create_table(
        "landmark_samples",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("signal_id", sa.String(length=36), nullable=False),
        sa.Column("variant_id", sa.String(length=36), nullable=True),
        sa.Column("video_id", sa.String(length=36), nullable=True),
        sa.Column("file_path", sa.String(length=2048), nullable=False),
        sa.Column("frame_count", sa.Integer(), nullable=True),
        sa.Column("fps", sa.Float(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["signal_id"], ["signals.id"], ondelete="CASCADE", name="fk_landmark_samples_signal_id"
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["signal_variants.id"],
            ondelete="SET NULL",
            name="fk_landmark_samples_variant_id",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"], ["videos.id"], ondelete="SET NULL", name="fk_landmark_samples_video_id"
        ),
    )
    op.create_index("ix_landmark_samples_signal_id", "landmark_samples", ["signal_id"])
    op.create_index("ix_landmark_samples_video_id", "landmark_samples", ["video_id"])

    op.create_table(
        "validations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("signal_id", sa.String(length=36), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("validator", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["signal_id"], ["signals.id"], ondelete="CASCADE", name="fk_validations_signal_id"
        ),
        sa.CheckConstraint(
            "decision IN ('approved', 'rejected', 'corrected', 'needs_review')",
            name="ck_validations_decision",
        ),
    )
    op.create_index("ix_validations_signal_id", "validations", ["signal_id"])

    op.create_table(
        "training_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("dataset_version", sa.String(length=64), nullable=False),
        sa.Column("base_model", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
    )
    op.create_index("ix_training_runs_dataset_version", "training_runs", ["dataset_version"])

    op.create_table(
        "model_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("dataset_version", sa.String(length=64), nullable=True),
        sa.Column("signals_count", sa.Integer(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="training"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("file_path", sa.String(length=2048), nullable=True),
        sa.UniqueConstraint("version", name="uq_model_versions_version"),
    )

    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("related_signal", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.UniqueConstraint("task_id", name="uq_agent_tasks_task_id"),
    )
    op.create_index("ix_agent_tasks_type", "agent_tasks", ["type"])

    op.create_table(
        "agent_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_events_event_type", "agent_events", ["event_type"])
    op.create_index("ix_agent_events_timestamp", "agent_events", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_agent_events_timestamp", table_name="agent_events")
    op.drop_index("ix_agent_events_event_type", table_name="agent_events")
    op.drop_table("agent_events")

    op.drop_index("ix_agent_tasks_type", table_name="agent_tasks")
    op.drop_table("agent_tasks")

    op.drop_table("model_versions")

    op.drop_index("ix_training_runs_dataset_version", table_name="training_runs")
    op.drop_table("training_runs")

    op.drop_index("ix_validations_signal_id", table_name="validations")
    op.drop_table("validations")

    op.drop_index("ix_landmark_samples_video_id", table_name="landmark_samples")
    op.drop_index("ix_landmark_samples_signal_id", table_name="landmark_samples")
    op.drop_table("landmark_samples")

    op.drop_index("ix_signal_variants_signal_id", table_name="signal_variants")
    op.drop_table("signal_variants")

    op.drop_index("ix_signals_status", table_name="signals")
    op.drop_index("ix_signals_concept", table_name="signals")
    op.drop_table("signals")

    op.drop_index("ix_videos_processing_status", table_name="videos")
    op.drop_index("ix_videos_source_id", table_name="videos")
    op.drop_table("videos")

    op.drop_index("ix_sources_source_type", table_name="sources")
    op.drop_table("sources")

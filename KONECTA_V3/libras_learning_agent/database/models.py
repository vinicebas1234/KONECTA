"""Modelos SQLAlchemy 2.0 (`Mapped`/`mapped_column`) do Libras Learning Agent.

Mesmo estilo de `app_backend/models/*.py`, mas com `Base` própria — nada é
importado de `app_backend`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from libras_learning_agent.database.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Source(Base):
    """Fonte de pesquisa (dicionário, vídeo, artigo etc.) de onde um sinal veio."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    license: Mapped[str | None] = mapped_column(String(128), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reliability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    usage_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    videos: Mapped[list["Video"]] = relationship("Video", back_populates="source")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Source id={self.id} title={self.title!r}>"


class SignalSource(Base):
    """Vínculo Signal<->Source: quais fontes sustentam um sinal candidato.

    Ciclo 5 (`agent/learn_signal.py`): sem isso não dá para um humano revisar
    um candidato em VALIDATION_REQUIRED e ver de onde ele veio.
    `UniqueConstraint` evita duplicar o vínculo se `learn_signal` rodar de
    novo sobre as mesmas fontes já registradas (dedup do Ciclo 3).
    """

    __tablename__ = "signal_sources"
    __table_args__ = (
        UniqueConstraint("signal_id", "source_id", name="uq_signal_sources_signal_id_source_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    signal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("signals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SignalSource signal_id={self.signal_id} source_id={self.source_id}>"


class Video(Base):
    """Vídeo (remoto ou local) associado a uma fonte, candidato a extração de landmarks."""

    __tablename__ = "videos"
    __table_args__ = (Index("ix_videos_processing_status", "processing_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # URL remota ou caminho local — o mesmo campo cobre os dois casos.
    url_or_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)  # segundos
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    license: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # valores esperados: pending, downloading, downloaded, processing, processed, failed
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped["Source | None"] = relationship("Source", back_populates="videos")
    landmark_samples: Mapped[list["LandmarkSample"]] = relationship(
        "LandmarkSample", back_populates="video"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Video id={self.id} status={self.processing_status}>"


class Signal(Base):
    """Um sinal de Libras candidato/descoberto pelo agente.

    Valores esperados de `status` (string livre, documentado aqui em vez de
    Enum de banco para não travar quem for adicionar um estado novo):
    DISCOVERED, ANALYZING, CANDIDATE, VALIDATION_REQUIRED, VALIDATED,
    TRAINING, EVALUATED, PRODUCTION, REJECTED, FAILED, ARCHIVED.
    """

    __tablename__ = "signals"
    __table_args__ = (Index("ix_signals_status", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    concept: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DISCOVERED")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    variants: Mapped[list["SignalVariant"]] = relationship(
        "SignalVariant", back_populates="signal", cascade="all, delete-orphan"
    )
    landmark_samples: Mapped[list["LandmarkSample"]] = relationship(
        "LandmarkSample", back_populates="signal", cascade="all, delete-orphan"
    )
    validations: Mapped[list["Validation"]] = relationship(
        "Validation", back_populates="signal", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Signal id={self.id} concept={self.concept!r} status={self.status}>"


class SignalVariant(Base):
    """Variante regional/contextual de um sinal (ex. mesma palavra, sinal diferente por região)."""

    __tablename__ = "signal_variants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    signal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("signals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    context: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    signal: Mapped["Signal"] = relationship("Signal", back_populates="variants")
    landmark_samples: Mapped[list["LandmarkSample"]] = relationship(
        "LandmarkSample", back_populates="variant"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SignalVariant id={self.id} name={self.name!r}>"


class LandmarkSample(Base):
    """Landmarks extraídos (MediaPipe) de um vídeo para um sinal/variante."""

    __tablename__ = "landmark_samples"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    signal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("signals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("signal_variants.id", ondelete="SET NULL"), nullable=True
    )
    # SET NULL, não CASCADE: os landmarks extraídos continuam valiosos mesmo
    # que o registro do vídeo de origem seja removido depois.
    video_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("videos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    file_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    frame_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    signal: Mapped["Signal"] = relationship("Signal", back_populates="landmark_samples")
    variant: Mapped["SignalVariant | None"] = relationship(
        "SignalVariant", back_populates="landmark_samples"
    )
    video: Mapped["Video | None"] = relationship("Video", back_populates="landmark_samples")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LandmarkSample id={self.id} signal_id={self.signal_id}>"


class Validation(Base):
    """Decisão humana sobre um sinal candidato."""

    __tablename__ = "validations"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('approved', 'rejected', 'corrected', 'needs_review')",
            name="ck_validations_decision",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    signal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("signals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    validator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    signal: Mapped["Signal"] = relationship("Signal", back_populates="validations")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Validation id={self.id} decision={self.decision}>"


class TrainingRun(Base):
    """Execução de treino de um modelo sobre um dataset versionado."""

    __tablename__ = "training_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    base_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # valores esperados: pending, running, completed, failed
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TrainingRun id={self.id} status={self.status}>"


class ModelVersion(Base):
    """Versão de modelo produzida por um treino (ex. `model_v001`).

    Isolamento: `file_path` deve viver sob `libras_learning_agent/models/`,
    nunca sob `KONECTA_V3/models/` — ver `core/config.py` e
    `KONECTA_V3/models/LEIA-ME.md`.
    """

    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("version", name="uq_model_versions_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signals_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # valores esperados: training, evaluated, production, archived, rolled_back
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="training")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ModelVersion id={self.id} version={self.version}>"


class AgentTask(Base):
    """Tarefa de trabalho do agente (pesquisar, extrair, treinar...)."""

    __tablename__ = "agent_tasks"
    __table_args__ = (UniqueConstraint("task_id", name="uq_agent_tasks_task_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(String(36), nullable=False, default=_uuid)
    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # também referido como "concept" na spec: o sinal ao qual a tarefa se relaciona.
    related_signal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AgentTask id={self.id} type={self.type} status={self.status}>"


class AgentEvent(Base):
    """Evento emitido pelo agente durante seu ciclo de trabalho.

    Valores esperados de `event_type`: research_started, research_completed,
    source_found, candidate_created, video_found, video_processed,
    landmarks_extracted, validation_requested, validation_completed,
    training_started, training_completed, evaluation_completed,
    model_promoted, error.
    """

    __tablename__ = "agent_events"
    __table_args__ = (Index("ix_agent_events_event_type", "event_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AgentEvent id={self.id} event_type={self.event_type}>"

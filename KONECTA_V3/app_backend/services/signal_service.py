"""Serviço de sinais e seed de modelos."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app_backend.config import settings
from app_backend.models.ml_model import MLModel
from app_backend.models.signal import Signal
from app_backend.models.user import User
from app_backend.schemas.signal import SignalResponse, SignalsListResponse
from app_backend.schemas.webhook import WebhookSignalRequest, WebhookSignalResponse

logger = logging.getLogger("konecta.backend.signals")


def _dt_iso(dt: datetime | None) -> str:
    if dt is None:
        return datetime.now(timezone.utc).isoformat()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).isoformat()
    return dt.isoformat()


def ensure_seed_model(db: Session) -> MLModel:
    """Garante pelo menos o modelo konecta_v3 v1 disponível."""
    stmt = select(MLModel).where(MLModel.name == "konecta_v3", MLModel.version == "1")
    existing = db.execute(stmt).scalar_one_or_none()
    if existing:
        if not existing.is_available:
            existing.is_available = True
            db.commit()
            db.refresh(existing)
        return existing

    model = MLModel(
        name="konecta_v3",
        version="1",
        path="models/konecta_v3",
        is_available=True,
        accuracy=None,
        metadata_json={"seeded": True, "description": "Modelo padrão KONECTA V3"},
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    logger.info("seed_model_created name=konecta_v3 version=1")
    return model


def get_or_create_user(
    db: Session, user_id: str, username: str | None = None
) -> User:
    user = db.get(User, user_id)
    if user:
        return user
    uname = username or f"user_{user_id[:8]}"
    # Evita colisão de username
    clash = db.execute(select(User).where(User.username == uname)).scalar_one_or_none()
    if clash:
        uname = f"{uname}_{user_id[:4]}"
    user = User(id=user_id, username=uname, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("user_auto_created id=%s username=%s", user_id, uname)
    return user


def list_signals(
    db: Session,
    user_id: str | None = None,
    page: int = 1,
    page_size: int | None = None,
) -> SignalsListResponse:
    page_size = page_size or settings.signals_default_page_size
    page_size = min(max(page_size, 1), settings.signals_max_page_size)
    page = max(page, 1)

    stmt = select(Signal)
    count_stmt = select(func.count()).select_from(Signal)
    if user_id:
        stmt = stmt.where(Signal.user_id == user_id)
        count_stmt = count_stmt.where(Signal.user_id == user_id)

    total = int(db.execute(count_stmt).scalar_one())
    stmt = (
        stmt.order_by(Signal.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = db.execute(stmt).scalars().all()

    items = [
        SignalResponse(
            id=s.id,
            user_id=s.user_id,
            signal_label=s.signal_label,
            confidence=s.confidence,
            latency_ms=s.latency_ms,
            model_used=s.model_used,
            raw_payload=s.raw_payload,
            created_at=_dt_iso(s.created_at),
        )
        for s in rows
    ]
    return SignalsListResponse(
        items=items, total=total, page=page, page_size=page_size, user_id=user_id
    )


def record_signal(db: Session, payload: WebhookSignalRequest) -> WebhookSignalResponse:
    """Persiste um sinal reconhecido (webhook N8N)."""
    get_or_create_user(db, payload.user_id, username=payload.username)

    signal = Signal(
        user_id=payload.user_id,
        signal_label=payload.signal_label,
        confidence=payload.confidence,
        latency_ms=payload.latency_ms,
        model_used=payload.model_used or "konecta_v3",
        raw_payload=payload.raw_payload,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)

    logger.info(
        "signal_recorded id=%s user=%s label=%s conf=%.3f",
        signal.id,
        signal.user_id,
        signal.signal_label,
        signal.confidence,
    )
    return WebhookSignalResponse(
        ok=True,
        signal_id=signal.id,
        user_id=signal.user_id,
        created_at=_dt_iso(signal.created_at),
    )


def list_available_models(db: Session) -> list[MLModel]:
    stmt = (
        select(MLModel)
        .where(MLModel.is_available.is_(True))
        .order_by(MLModel.name, MLModel.version)
    )
    return list(db.execute(stmt).scalars().all())

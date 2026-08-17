"""POST /api/webhook/signal-recognized — protegido por API key (N8N)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app_backend.database import get_db
from app_backend.middleware.auth import RequireAPIKey
from app_backend.schemas.webhook import WebhookSignalRequest, WebhookSignalResponse
from app_backend.services import signal_service

router = APIRouter()


@router.post("/webhook/signal-recognized", response_model=WebhookSignalResponse)
def webhook_signal_recognized(
    payload: WebhookSignalRequest,
    _api_key: RequireAPIKey,
    db: Session = Depends(get_db),
) -> WebhookSignalResponse:
    """Recebe evento de sinal reconhecido do N8N / pipeline (requer X-API-Key)."""
    return signal_service.record_signal(db, payload)

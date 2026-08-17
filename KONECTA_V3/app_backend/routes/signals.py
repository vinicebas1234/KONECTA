"""GET /api/signals — lista sinais (API key opcional)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app_backend.config import settings
from app_backend.database import get_db
from app_backend.middleware.auth import optional_api_key
from app_backend.schemas.signal import SignalsListResponse
from app_backend.services import signal_service

router = APIRouter()


@router.get("/signals", response_model=SignalsListResponse)
def get_signals(
    user_id: str | None = Query(default=None, description="Filtrar por user_id"),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=500),
    _api_key: Optional[str] = Depends(optional_api_key),
    db: Session = Depends(get_db),
) -> SignalsListResponse:
    """Lista sinais reconhecidos. Filtro opcional por user_id."""
    size = page_size or settings.signals_default_page_size
    return signal_service.list_signals(
        db, user_id=user_id, page=page, page_size=size
    )

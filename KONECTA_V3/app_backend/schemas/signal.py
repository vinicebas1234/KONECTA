"""Schemas de sinais."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SignalResponse(BaseModel):
    """Representação de um sinal armazenado."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    signal_label: str
    confidence: float
    latency_ms: int | None = None
    model_used: str | None = None
    raw_payload: dict[str, Any] | None = None
    created_at: str


class SignalsListResponse(BaseModel):
    """Lista paginada de sinais."""

    items: list[SignalResponse]
    total: int
    page: int = 1
    page_size: int = Field(default=50)
    user_id: str | None = None

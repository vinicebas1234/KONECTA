"""Schemas do webhook de sinal reconhecido."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WebhookSignalRequest(BaseModel):
    """Payload de POST /api/webhook/signal-recognized (N8N)."""

    user_id: str = Field(..., min_length=1, description="ID do usuário (UUID)")
    signal_label: str = Field(..., min_length=1, max_length=128)
    confidence: float = Field(..., ge=0.0, le=1.0)
    latency_ms: int | None = Field(default=None, ge=0)
    model_used: str | None = None
    raw_payload: dict[str, Any] | None = None
    # Permite criar usuário on-the-fly se ainda não existir
    username: str | None = Field(
        default=None, description="Username opcional para auto-provisionar usuário"
    )


class WebhookSignalResponse(BaseModel):
    """Confirmação do webhook."""

    ok: bool = True
    signal_id: str
    user_id: str
    created_at: str

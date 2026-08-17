"""Schemas de métricas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MetricsPayload(BaseModel):
    """Payload de POST /api/metrics."""

    name: str = Field(..., min_length=1, max_length=128)
    value: float
    tags: dict[str, Any] | None = None
    user_id: str | None = None
    timestamp: str | None = Field(
        default=None, description="ISO-8601; se omitido usa agora (UTC)"
    )


class MetricsResponse(BaseModel):
    """Confirmação de ingestão de métrica."""

    accepted: bool = True
    name: str
    value: float
    recorded_at: str

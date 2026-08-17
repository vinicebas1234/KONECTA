"""Schemas de health check."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Resposta de GET /api/health."""

    status: str = Field(..., description="ok | degraded | error")
    db: bool = Field(..., description="Conectividade com o banco")
    version: str
    uptime_seconds: float
    environment: str | None = None
    performance: Optional[dict[str, Any]] = Field(
        default=None,
        description="Snapshot de performance (request_count, errors, avg_latency_ms)",
    )

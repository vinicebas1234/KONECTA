"""GET /api/health."""

from __future__ import annotations

import time

from fastapi import APIRouter

from app_backend import __version__
from app_backend.config import settings
from app_backend.database import check_db_connectivity
from app_backend.middleware.logging_middleware import get_perf_snapshot
from app_backend.schemas.health import HealthResponse

router = APIRouter()

_STARTED_AT = time.monotonic()


def check_db_health() -> dict:
    """Retorna status simples (usado pelo /health legado)."""
    return {"status": "ok" if check_db_connectivity() else "error"}


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Health check: status, DB, versão, uptime e snapshot de performance."""
    db_ok = check_db_connectivity()
    uptime = time.monotonic() - _STARTED_AT
    status = "ok" if db_ok else "degraded"
    return HealthResponse(
        status=status,
        db=db_ok,
        version=settings.app_version or __version__,
        uptime_seconds=round(uptime, 2),
        environment=settings.environment,
        performance=get_perf_snapshot(),
    )

"""POST /api/metrics — protegido por API key."""

from __future__ import annotations

from fastapi import APIRouter

from app_backend.middleware.auth import RequireAPIKey
from app_backend.schemas.metrics import MetricsPayload, MetricsResponse
from app_backend.services import metrics_service

router = APIRouter()


@router.post("/metrics", response_model=MetricsResponse)
def post_metrics(
    payload: MetricsPayload,
    _api_key: RequireAPIKey,
) -> MetricsResponse:
    """Ingere uma métrica de performance / negócio (requer X-API-Key)."""
    return metrics_service.ingest_metric(payload)

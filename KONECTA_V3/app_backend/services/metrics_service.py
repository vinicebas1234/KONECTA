"""Serviço de métricas (ingestão + Prometheus opcional)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app_backend.config import settings
from app_backend.schemas.metrics import MetricsPayload, MetricsResponse

logger = logging.getLogger("konecta.backend.metrics")

# Buffer em memória (útil quando não há tabela dedicada de métricas)
_METRICS_BUFFER: list[dict[str, Any]] = []
_BUFFER_MAX = 10_000

_prom_counters: dict[str, Any] = {}


def _get_prom_counter(name: str):
    if not settings.prometheus_enabled:
        return None
    try:
        from prometheus_client import Counter

        if name not in _prom_counters:
            safe = name.replace(".", "_").replace("-", "_")
            _prom_counters[name] = Counter(
                f"konecta_{safe}_total",
                f"KONECTA metric: {name}",
                ["tag"],
            )
        return _prom_counters[name]
    except Exception:
        return None


def ingest_metric(payload: MetricsPayload) -> MetricsResponse:
    """Aceita uma métrica, registra em log/buffer e atualiza Prometheus."""
    recorded_at = payload.timestamp or datetime.now(timezone.utc).isoformat()
    entry = {
        "name": payload.name,
        "value": payload.value,
        "tags": payload.tags or {},
        "user_id": payload.user_id,
        "recorded_at": recorded_at,
    }
    _METRICS_BUFFER.append(entry)
    if len(_METRICS_BUFFER) > _BUFFER_MAX:
        del _METRICS_BUFFER[: len(_METRICS_BUFFER) - _BUFFER_MAX]

    logger.info(
        "metric_ingested",
        extra={
            "metric_name": payload.name,
            "metric_value": payload.value,
            "user_id": payload.user_id,
        },
    )

    counter = _get_prom_counter(payload.name)
    if counter is not None:
        tag = (payload.tags or {}).get("source", "default")
        try:
            counter.labels(tag=str(tag)).inc(payload.value if payload.value > 0 else 1)
        except Exception:
            pass

    return MetricsResponse(
        accepted=True,
        name=payload.name,
        value=payload.value,
        recorded_at=recorded_at,
    )


def recent_metrics(limit: int = 100) -> list[dict[str, Any]]:
    return list(_METRICS_BUFFER[-limit:])

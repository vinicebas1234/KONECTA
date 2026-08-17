"""Middleware de logging estruturado (JSON) + métricas de performance."""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app_backend.config import settings

# Contadores simples em memória para /api/health e Prometheus-style export
REQUEST_COUNT = 0
REQUEST_ERRORS = 0
REQUEST_LATENCY_SUM = 0.0

# --- Prometheus (opcional, mas instalado por padrão) ------------------------
_prom = None
try:  # pragma: no cover - dep optional
    from prometheus_client import Counter, Histogram

    _prom = {
        "requests": Counter(
            "konecta_http_requests_total",
            "Total de requests HTTP por rota",
            ["method", "path", "status"],
        ),
        "duration": Histogram(
            "konecta_http_request_duration_seconds",
            "Latência de requests HTTP em segundos",
            ["method", "path"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
        ),
    }
except Exception:  # noqa: BLE001
    _prom = None


def _record_prometheus(
    method: str, path: str, status: int, duration_seconds: float
) -> None:
    if _prom is None:
        return
    try:
        _prom["requests"].labels(method=method, path=path, status=str(status)).inc()
        _prom["duration"].labels(method=method, path=path).observe(duration_seconds)
    except Exception:  # noqa: BLE001
        pass


class JsonFormatter(logging.Formatter):
    """Formata LogRecord como JSON em uma linha."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "method", "path", "status", "latency_ms", "client"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> logging.Logger:
    """Configura logging raiz (JSON ou texto) e retorna logger da app."""
    Path(settings.log_dir).mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    if settings.log_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
    root.addHandler(handler)

    # Arquivo rotativo simples (append)
    file_handler = logging.FileHandler(
        Path(settings.log_dir) / "app_backend.log", encoding="utf-8"
    )
    file_handler.setFormatter(JsonFormatter() if settings.log_json else handler.formatter)
    root.addHandler(file_handler)

    return logging.getLogger("konecta.backend")


logger = logging.getLogger("konecta.backend")


def report_error(exc: BaseException, context: dict[str, Any] | None = None) -> None:
    """Hook de error tracking (Sentry se configurado; senão log JSON)."""
    payload = {
        "error": str(exc),
        "type": type(exc).__name__,
        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        "context": context or {},
    }
    logger.error("unhandled_error %s", json.dumps(payload, ensure_ascii=False))

    if settings.sentry_dsn:
        try:
            import sentry_sdk

            with sentry_sdk.push_scope() as scope:
                for k, v in (context or {}).items():
                    scope.set_extra(k, v)
                sentry_sdk.capture_exception(exc)
        except Exception:  # pragma: no cover
            logger.warning("Falha ao enviar erro ao Sentry")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Loga cada request em JSON com latency_ms e request_id."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        global REQUEST_COUNT, REQUEST_ERRORS, REQUEST_LATENCY_SUM

        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as exc:
            REQUEST_ERRORS += 1
            report_error(
                exc,
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000.0
            REQUEST_COUNT += 1
            REQUEST_LATENCY_SUM += latency_ms
            if status_code >= 500:
                REQUEST_ERRORS += 1
            _record_prometheus(
                request.method,
                request.scope.get("route") and request.scope["route"].path
                or request.url.path,
                status_code,
                latency_ms / 1000.0,
            )
            logger.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": status_code,
                    "latency_ms": round(latency_ms, 2),
                    "client": request.client.host if request.client else None,
                },
            )


def get_perf_snapshot() -> dict[str, Any]:
    """Snapshot de métricas de performance em memória."""
    avg = (REQUEST_LATENCY_SUM / REQUEST_COUNT) if REQUEST_COUNT else 0.0
    return {
        "request_count": REQUEST_COUNT,
        "request_errors": REQUEST_ERRORS,
        "avg_latency_ms": round(avg, 2),
    }

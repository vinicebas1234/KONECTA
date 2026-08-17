"""Rate limiting in-memory (token bucket) + integração opcional com slowapi.

Por padrão usa um token bucket por IP/chave. Se `slowapi` estiver instalado,
o limiter do FastAPI pode ser plugado no app (ver main.py).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app_backend.config import settings


def _parse_limit(spec: str) -> tuple[int, float]:
    """Parse '100/minute' | '10/second' | '1000/hour' -> (max_tokens, refill_per_sec)."""
    raw = (spec or "100/minute").strip().lower()
    try:
        count_str, period = raw.split("/", 1)
        count = int(count_str)
    except ValueError:
        count, period = 100, "minute"

    period_seconds = {
        "second": 1.0,
        "seconds": 1.0,
        "sec": 1.0,
        "minute": 60.0,
        "minutes": 60.0,
        "min": 60.0,
        "hour": 3600.0,
        "hours": 3600.0,
        "hr": 3600.0,
        "day": 86400.0,
        "days": 86400.0,
    }.get(period, 60.0)

    refill_per_sec = count / period_seconds
    return count, refill_per_sec


class TokenBucket:
    """Token bucket thread-safe por chave."""

    def __init__(self, capacity: int, refill_per_sec: float) -> None:
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self.tokens = float(capacity)
        self.updated_at = time.monotonic()
        self._lock = threading.Lock()

    def allow(self, cost: float = 1.0) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self.updated_at
            self.updated_at = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_sec)
            if self.tokens >= cost:
                self.tokens -= cost
                return True
            return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware de rate limit por IP (ou X-API-Key se presente)."""

    def __init__(self, app, limit_spec: str | None = None) -> None:  # noqa: ANN001
        super().__init__(app)
        capacity, refill = _parse_limit(limit_spec or settings.rate_limit)
        self.capacity = capacity
        self.refill = refill
        self._buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(self.capacity, self.refill)
        )
        self._lock = threading.Lock()
        # Rotas isentas (health)
        self.exempt_paths = {"/api/health", "/health", "/docs", "/openapi.json", "/redoc"}

    def _client_key(self, request: Request) -> str:
        api_key = request.headers.get(settings.api_key_header) or request.headers.get(
            "X-API-Key"
        )
        if api_key:
            return f"key:{api_key[:16]}"
        if settings.trusted_proxy:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                return f"ip:{forwarded.split(',')[0].strip()}"
        client = request.client.host if request.client else "unknown"
        return f"ip:{client}"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if path in self.exempt_paths or request.method == "OPTIONS":
            return await call_next(request)

        key = self._client_key(request)
        with self._lock:
            bucket = self._buckets[key]
        if not bucket.allow():
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Rate limit excedido ({settings.rate_limit}). "
                        "Tente novamente em breve."
                    )
                },
                headers={"Retry-After": "60"},
            )
        return await call_next(request)


# --- slowapi helpers (opcional) ---------------------------------------------

def try_create_slowapi_limiter():  # noqa: ANN201
    """Retorna (Limiter, _rate_limit_exceeded_handler) se slowapi estiver disponível."""
    try:
        from slowapi import Limiter
        from slowapi.errors import RateLimitExceeded
        from slowapi.util import get_remote_address

        limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])
        return limiter, RateLimitExceeded
    except ImportError:
        return None, None

"""KONECTA Intelligence Hub — FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app_backend import __version__
from app_backend.config import settings
from app_backend.database import get_session_factory, init_db
from app_backend.middleware.logging_middleware import (
    LoggingMiddleware,
    report_error,
    setup_logging,
)
from app_backend.middleware.rate_limit import RateLimitMiddleware
from app_backend.routes import build_api_router
from app_backend.services.signal_service import ensure_seed_model

logger = logging.getLogger("konecta.backend")


def _init_sentry() -> None:
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            release=f"konecta-backend@{settings.app_version}",
            integrations=[FastApiIntegration()],
            traces_sample_rate=0.1 if settings.is_production else 0.0,
        )
        logger.info("Sentry inicializado")
    except Exception as exc:  # pragma: no cover
        logger.warning("Sentry não disponível: %s", exc)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown hooks."""
    setup_logging()
    _init_sentry()
    logger.info(
        "starting app=%s version=%s env=%s",
        settings.app_name,
        settings.app_version,
        settings.environment,
    )
    try:
        init_db()
        db = get_session_factory()()
        try:
            ensure_seed_model(db)
        finally:
            db.close()
    except Exception as exc:
        report_error(exc, {"phase": "startup"})
        raise

    yield
    logger.info("shutdown complete")


def create_app() -> FastAPI:
    """Factory da aplicação FastAPI."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version or __version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=settings.cors_methods_list,
        allow_headers=settings.cors_headers_list or ["*"],
    )

    # Rate limiting — token bucket em processo (sempre ativo, thread-safe).
    #
    # NOTA: slowapi foi testado nesta stack (FastAPI 0.141/Starlette nova) e
    # seu middleware não enxerga handlers de routers incluídos
    # (`_IncludedRouter` sem `.endpoint`), tornando a checagem um no-op.
    # O token bucket abaixo é confiável e isenta health/docs. Para limites
    # por rota com slowapi, use `@limiter.limit(...)` diretamente no handler.
    app.add_middleware(RateLimitMiddleware)
    logger.info("Rate limit via TokenBucket: %s", settings.rate_limit)

    # Logging / request_id / latency
    app.add_middleware(LoggingMiddleware)

    # Rotas
    app.include_router(build_api_router(), prefix=settings.api_prefix)

    @app.get("/")
    def root() -> dict:
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health",
            "metrics": "/metrics",
        }

    # /health legado — o docker-compose/healthcheck antigo do repo usa esse path.
    from app_backend.routes.health import check_db_health

    @app.get("/health", include_in_schema=False)
    def legacy_health() -> dict:
        return check_db_health()

    # Prometheus: GET /metrics (formato de texto). A instrumentação de
    # request_count/latency vive em middleware/logging_middleware.py.
    if settings.prometheus_enabled:
        try:
            from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
            from starlette.responses import Response

            @app.get("/metrics", include_in_schema=False)
            def metrics() -> Response:
                return Response(
                    content=generate_latest(), media_type=CONTENT_TYPE_LATEST
                )
        except ImportError:
            logger.warning(
                "prometheus_client não instalado — endpoint /metrics desabilitado"
            )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app_backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=not settings.is_production,
        log_level=settings.log_level.lower(),
    )

"""API routers."""

from fastapi import APIRouter

from app_backend.routes import health, metrics, models, signals, webhook


def build_api_router() -> APIRouter:
    """Monta o router /api com todas as rotas."""
    api = APIRouter()
    api.include_router(health.router, tags=["health"])
    api.include_router(metrics.router, tags=["metrics"])
    api.include_router(signals.router, tags=["signals"])
    api.include_router(models.router, tags=["models"])
    api.include_router(webhook.router, tags=["webhook"])
    return api

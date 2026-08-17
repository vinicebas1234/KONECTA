"""GET /api/models/available — público."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app_backend.database import get_db
from app_backend.schemas.model import ModelResponse, ModelsListResponse
from app_backend.services import signal_service

router = APIRouter()


def _model_to_response(m) -> ModelResponse:  # noqa: ANN001
    return ModelResponse(
        id=m.id,
        name=m.name,
        version=m.version,
        path=m.path,
        is_available=m.is_available,
        accuracy=m.accuracy,
        metadata_json=m.metadata_json,
        created_at=m.created_at.isoformat() if m.created_at else "",
        updated_at=m.updated_at.isoformat() if m.updated_at else "",
    )


@router.get("/models/available", response_model=ModelsListResponse)
def get_available_models(db: Session = Depends(get_db)) -> ModelsListResponse:
    """Retorna modelos ML marcados como disponíveis."""
    rows = signal_service.list_available_models(db)
    items = [_model_to_response(m) for m in rows]
    return ModelsListResponse(items=items, total=len(items))

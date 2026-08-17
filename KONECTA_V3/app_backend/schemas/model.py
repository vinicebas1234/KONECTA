"""Schemas de modelos ML."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ModelResponse(BaseModel):
    """Modelo ML disponível."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    version: str
    path: str | None = None
    is_available: bool
    accuracy: float | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: str
    updated_at: str


class ModelsListResponse(BaseModel):
    """Lista de modelos disponíveis."""

    items: list[ModelResponse]
    total: int

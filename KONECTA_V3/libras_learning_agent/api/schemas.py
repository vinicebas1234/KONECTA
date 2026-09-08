"""Schemas Pydantic de request/response da API do Libras Learning Agent (Ciclo 6).

Arquivo separado de `app.py` só porque são vários schemas — nada de lógica
aqui, só forma dos dados. `from_attributes=True` nos schemas de saída permite
devolver o objeto SQLAlchemy (`Signal`/`Source`/`AgentEvent`) direto, sem
montar dict à mão em cada rota.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ResearchRequest(BaseModel):
    concept: str
    max_results: Optional[int] = None


class ResearchResponse(BaseModel):
    signal_id: str
    concept: str
    status: str
    # Vêm do payload do AgentEvent(research_completed), se existir — por isso
    # opcionais (um Signal que falhou antes de chegar lá não tem esses dados).
    classification: Optional[str] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    sources_count: Optional[int] = None


class CandidateSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    concept: str
    status: str
    created_at: datetime
    updated_at: datetime


class SignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    concept: str
    category: Optional[str] = None
    description: Optional[str] = None
    status: str
    confidence: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    url: Optional[str] = None
    title: Optional[str] = None


class AgentEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_type: str
    payload: Optional[dict[str, Any]] = None
    timestamp: datetime


class CandidateDetail(SignalOut):
    sources: list[SourceOut]
    events: list[AgentEventOut]


class ValidationRequest(BaseModel):
    decision: str
    validator: str
    notes: Optional[str] = None

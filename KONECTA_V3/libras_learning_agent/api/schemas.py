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


# --------------------------------------------------------------------- Ciclo 8: progresso/acurácia ---


class ModelVersionSummary(BaseModel):
    """Resumo de um `ModelVersion` — `top1_accuracy`/`top5_accuracy` são extraídos
    de `metrics` com `.get()` defensivo (não presume que todo `metrics` tem
    exatamente esse formato; um ciclo futuro pode gravar métricas diferentes).
    """

    id: str
    version: str
    dataset_version: Optional[str] = None
    signals_count: Optional[int] = None
    status: str
    created_at: datetime
    top1_accuracy: Optional[float] = None
    top5_accuracy: Optional[float] = None


class TrainingRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_version: str
    base_model: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metrics: Optional[dict[str, Any]] = None


class ModelVersionDetail(ModelVersionSummary):
    # dict `metrics` inteiro (o resumo acima só expõe top1/top5). `training_runs`:
    # não há FK entre ModelVersion e TrainingRun hoje, então é a lista de
    # TrainingRun com o mesmo dataset_version — correspondência, não vínculo garantido.
    metrics: Optional[dict[str, Any]] = None
    file_path: Optional[str] = None
    training_runs: list[TrainingRunOut] = []


class ModelPromoteResponse(ModelVersionSummary):
    # Preenchido quando promover este modelo rebaixou automaticamente outro
    # ModelVersion que estava em "production" pra "archived" (no máximo um
    # "production" por vez no bookkeeping do LLA). None se não havia nenhum.
    demoted_model_id: Optional[str] = None


class StatsResponse(BaseModel):
    signals_by_status: dict[str, int]
    signals_total: int
    models_by_status: dict[str, int]
    models_total: int


# --------------------------------------------------------------------- Ciclo 11: predição ---


class PredictionRankingItem(BaseModel):
    sign: str
    distance: float


class PredictResponse(BaseModel):
    # Rastreabilidade: qual ModelVersion (sempre o "production" no momento da
    # chamada, nunca outro status — ver api/app.py::predict) gerou este ranking.
    model_version_id: str
    model_version: str
    ranking: list[PredictionRankingItem]
    # Reaproveitados de HandExtractionResult (vision/hand_landmarks.py), não
    # recalculados: dizem ao chamador se a extração captou mão de verdade.
    frame_count: int
    detection_rate: float

"""Ciclo 6 do Libras Learning Agent: API HTTP isolada.

Processo, porta (padrão 8010 — `Settings.api_port`) e app FastAPI 100%
próprios do LLA. NUNCA montada dentro dos routers de `app_backend/` (prod,
prefixo `/api`, porta 8000) nem de `vision_lab/` (experimental, também porta
8000 por padrão) — ver `__main__.py` para o `uvicorn.run` que sobe este app
sozinho.

Rotas sob prefixo `/api/libras`, mais `GET /health` fora do prefixo.
"""

from __future__ import annotations

from typing import Generator, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from libras_learning_agent import __version__
from libras_learning_agent.agent.candidate_manager import (
    LEGAL_TRANSITIONS,
    IllegalTransitionError,
    get_signal,
    register_validation,
)
from libras_learning_agent.agent.learn_signal import learn_signal
from libras_learning_agent.api.schemas import (
    AgentEventOut,
    CandidateDetail,
    CandidateSummary,
    ModelPromoteResponse,
    ModelVersionDetail,
    ModelVersionSummary,
    ResearchRequest,
    ResearchResponse,
    SignalOut,
    SourceOut,
    StatsResponse,
    TrainingRunOut,
    ValidationRequest,
)
from libras_learning_agent.database.db import get_db
from libras_learning_agent.database.models import AgentEvent, ModelVersion, Signal, SignalSource, Source, TrainingRun
from libras_learning_agent.research import SourceComparisonError, WebSearchError

# Estados de Signal.status: reaproveita as chaves de LEGAL_TRANSITIONS (Ciclo 2)
# em vez de duplicar a lista — são exatamente os 11 estados documentados em
# database/models.py, e ficam presos à mesma fonte da verdade.
SIGNAL_STATUSES: tuple[str, ...] = tuple(LEGAL_TRANSITIONS.keys())

# Estados de ModelVersion.status documentados em database/models.py (não há
# tabela de transições dedicada pra eles antes deste ciclo, então a lista vive
# só aqui — usada por GET /stats pra não omitir status sem nenhum ModelVersion.
MODEL_VERSION_STATUSES: tuple[str, ...] = ("training", "evaluated", "production", "archived", "rolled_back")

app = FastAPI(title="Libras Learning Agent API", version=__version__)


def get_session() -> Generator[Session, None, None]:
    """Uma `Session` por request, fechada no fim — reaproveita `database.db.get_db`
    (já faz `try/finally: session.close()`), não reimplementa o mesmo ciclo de vida.
    """
    yield from get_db()


# --------------------------------------------------------------------- exception handlers ---


@app.exception_handler(IllegalTransitionError)
async def _handle_illegal_transition(request: Request, exc: IllegalTransitionError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


async def _handle_external_service_error(request: Request, exc: Exception) -> JSONResponse:
    # WebSearchError/SourceComparisonError (research/, propagadas por
    # learn_signal): falha de serviço EXTERNO (busca web, Gemini) — não é bug
    # do LLA, por isso 502 (Bad Gateway) e não 500.
    return JSONResponse(status_code=502, content={"detail": str(exc)})


app.exception_handler(WebSearchError)(_handle_external_service_error)
app.exception_handler(SourceComparisonError)(_handle_external_service_error)


@app.exception_handler(ValueError)
async def _handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    # Única origem de ValueError neste ciclo: register_validation rejeitando
    # uma `decision` fora de approved/rejected/corrected/needs_review.
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# --------------------------------------------------------------------- rotas ---

router = APIRouter(prefix="/api/libras")


@app.get("/health")
def health() -> dict:
    """Liveness simples: nem banco, nem rede — só confirma que o processo responde."""
    return {"status": "ok", "version": __version__}


def _get_signal_or_404(session: Session, signal_id: str) -> Signal:
    signal = get_signal(session, signal_id)
    if signal is None:
        # Detectado aqui mesmo (não em camada mais funda) -> HTTPException direto
        # é o idiomático do FastAPI; não há motivo para inventar uma exceção
        # dedicada só para isto.
        raise HTTPException(status_code=404, detail=f"Signal {signal_id!r} não encontrado")
    return signal


def _events_for_signal(session: Session, signal_id: str) -> list[AgentEvent]:
    # Mesmo padrão já usado em tests/test_learn_signal.py: AgentEvent não tem
    # coluna signal_id própria (o vínculo vive dentro do JSON `payload`), então
    # filtra em Python em vez de expressão JSON específica de backend.
    all_events = session.scalars(select(AgentEvent)).all()
    matching = [e for e in all_events if e.payload and e.payload.get("signal_id") == signal_id]
    return sorted(matching, key=lambda e: e.timestamp)


@router.post("/research", response_model=ResearchResponse)
def research(body: ResearchRequest, session: Session = Depends(get_session)) -> ResearchResponse:
    kwargs = {} if body.max_results is None else {"max_results": body.max_results}
    signal = learn_signal(session, body.concept, **kwargs)

    # Campos de classificação vêm do payload do evento research_completed,
    # se existir (só existe no caminho de sucesso de learn_signal).
    completed = next(
        (e for e in _events_for_signal(session, signal.id) if e.event_type == "research_completed"), None
    )
    payload = completed.payload or {} if completed else {}

    return ResearchResponse(
        signal_id=signal.id,
        concept=signal.concept,
        status=signal.status,
        classification=payload.get("classification"),
        confidence=payload.get("confidence"),
        reasoning=payload.get("reasoning"),
        sources_count=payload.get("sources_count"),
    )


@router.get("/candidates", response_model=list[CandidateSummary])
def list_candidates(
    status: Optional[str] = None, limit: int = 50, session: Session = Depends(get_session)
) -> list[Signal]:
    query = select(Signal).order_by(Signal.created_at.desc()).limit(limit)
    if status is not None:
        query = query.where(Signal.status == status)
    return list(session.scalars(query).all())


@router.get("/candidates/{signal_id}", response_model=CandidateDetail)
def get_candidate(signal_id: str, session: Session = Depends(get_session)) -> CandidateDetail:
    signal = _get_signal_or_404(session, signal_id)

    sources = list(
        session.scalars(
            select(Source)
            .join(SignalSource, SignalSource.source_id == Source.id)
            .where(SignalSource.signal_id == signal_id)
        ).all()
    )
    events = _events_for_signal(session, signal_id)

    return CandidateDetail(
        **SignalOut.model_validate(signal).model_dump(),
        sources=[SourceOut.model_validate(s) for s in sources],
        events=[AgentEventOut.model_validate(e) for e in events],
    )


@router.post("/candidates/{signal_id}/validation", response_model=SignalOut)
def validate_candidate(
    signal_id: str, body: ValidationRequest, session: Session = Depends(get_session)
) -> Signal:
    signal = _get_signal_or_404(session, signal_id)

    # Decisão de design deliberada: um único endpoint cobre os 4 valores de
    # `decision` (approved/rejected/corrected/needs_review), reaproveitando
    # 1:1 a assinatura de `register_validation` (Ciclo 2, já testada) — em
    # vez de 4 rotas separadas (/validate, /reject, ...) como uma versão
    # antiga da spec sugeria. Nenhuma lógica de negócio nova aqui: o mapeamento
    # decision -> status legal é inteiramente de `candidate_manager`.
    register_validation(session, signal, body.decision, body.validator, notes=body.notes)
    return signal


# --------------------------------------------------------------------- Ciclo 8: progresso/acurácia ---
#
# Bookkeeping puro sobre o banco do LLA. "promover" um ModelVersion pra
# "production" aqui é só o dono do projeto marcando qual é o modelo de
# referência atual do LLA — NUNCA escreve em KONECTA_V3/models/ nem em
# qualquer coisa que app_central leia (isso continua vindo só de
# app_central/providers/export_signlab.py, fora do escopo do LLA).


def _model_summary(model: ModelVersion) -> ModelVersionSummary:
    metrics = model.metrics or {}
    return ModelVersionSummary(
        id=model.id,
        version=model.version,
        dataset_version=model.dataset_version,
        signals_count=model.signals_count,
        status=model.status,
        created_at=model.created_at,
        top1_accuracy=metrics.get("top1_accuracy"),
        top5_accuracy=metrics.get("top5_accuracy"),
    )


def _get_model_or_404(session: Session, model_id: str) -> ModelVersion:
    model = session.get(ModelVersion, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail=f"ModelVersion {model_id!r} não encontrado")
    return model


@router.get("/models", response_model=list[ModelVersionSummary])
def list_models(status: Optional[str] = None, session: Session = Depends(get_session)) -> list[ModelVersionSummary]:
    query = select(ModelVersion).order_by(ModelVersion.created_at.desc())
    if status is not None:
        query = query.where(ModelVersion.status == status)
    return [_model_summary(m) for m in session.scalars(query).all()]


@router.get("/models/{model_id}", response_model=ModelVersionDetail)
def get_model(model_id: str, session: Session = Depends(get_session)) -> ModelVersionDetail:
    model = _get_model_or_404(session, model_id)

    # Sem FK direta ModelVersion<->TrainingRun hoje: amarra por correspondência
    # de dataset_version (não é um vínculo garantido, só a melhor pista que temos).
    training_runs: list[TrainingRun] = []
    if model.dataset_version is not None:
        training_runs = list(
            session.scalars(
                select(TrainingRun).where(TrainingRun.dataset_version == model.dataset_version)
            ).all()
        )

    return ModelVersionDetail(
        **_model_summary(model).model_dump(),
        metrics=model.metrics,
        file_path=model.file_path,
        training_runs=[TrainingRunOut.model_validate(t) for t in training_runs],
    )


@router.post("/models/{model_id}/promote", response_model=ModelPromoteResponse)
def promote_model(model_id: str, session: Session = Depends(get_session)) -> ModelPromoteResponse:
    """Só permite `"evaluated" -> "production"` (mesmo espírito de LEGAL_TRANSITIONS
    do Ciclo 2, mas só 2 estados envolvidos aqui — não justifica uma tabela nova).

    Desempate: no máximo um ModelVersion "production" por vez no bookkeeping do
    LLA. Se já existir outro em "production", ele é rebaixado pra "archived"
    ANTES do novo ser promovido, na mesma sessão/commit (nunca dois em
    "production" simultaneamente, nem entre um commit e outro).
    """
    model = _get_model_or_404(session, model_id)
    if model.status != "evaluated":
        raise IllegalTransitionError(
            f"Transição ilegal: {model.status!r} -> 'production'. "
            "Só é permitido promover um ModelVersion em status 'evaluated'."
        )

    demoted_id: Optional[str] = None
    previous_production = session.scalars(
        select(ModelVersion).where(ModelVersion.status == "production")
    ).first()
    if previous_production is not None and previous_production.id != model.id:
        previous_production.status = "archived"
        session.add(previous_production)
        demoted_id = previous_production.id

    model.status = "production"
    session.add(model)
    session.commit()
    session.refresh(model)

    return ModelPromoteResponse(**_model_summary(model).model_dump(), demoted_model_id=demoted_id)


@router.post("/models/{model_id}/rollback", response_model=ModelVersionSummary)
def rollback_model(model_id: str, session: Session = Depends(get_session)) -> ModelVersionSummary:
    """Só permite `"production" -> "archived"`."""
    model = _get_model_or_404(session, model_id)
    if model.status != "production":
        raise IllegalTransitionError(
            f"Transição ilegal: {model.status!r} -> 'archived'. "
            "Só é permitido rollback de um ModelVersion em status 'production'."
        )

    model.status = "archived"
    session.add(model)
    session.commit()
    session.refresh(model)

    return _model_summary(model)


@router.get("/stats", response_model=StatsResponse)
def stats(session: Session = Depends(get_session)) -> StatsResponse:
    """Contagem de Signal por status (todos os 11 documentados, 0 pros sem sinal
    nenhum) e de ModelVersion por status — responde "como controlo o progresso".
    """
    signal_counts = dict(session.execute(select(Signal.status, func.count()).group_by(Signal.status)).all())
    signals_by_status = {status: signal_counts.get(status, 0) for status in SIGNAL_STATUSES}
    for status, count in signal_counts.items():  # status fora dos documentados: não descarta.
        signals_by_status.setdefault(status, count)

    model_counts = dict(
        session.execute(select(ModelVersion.status, func.count()).group_by(ModelVersion.status)).all()
    )
    models_by_status = {status: model_counts.get(status, 0) for status in MODEL_VERSION_STATUSES}
    for status, count in model_counts.items():
        models_by_status.setdefault(status, count)

    return StatsResponse(
        signals_by_status=signals_by_status,
        signals_total=sum(signals_by_status.values()),
        models_by_status=models_by_status,
        models_total=sum(models_by_status.values()),
    )


app.include_router(router)

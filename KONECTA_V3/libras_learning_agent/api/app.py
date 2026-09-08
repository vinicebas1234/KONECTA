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
from sqlalchemy import select
from sqlalchemy.orm import Session

from libras_learning_agent import __version__
from libras_learning_agent.agent.candidate_manager import IllegalTransitionError, get_signal, register_validation
from libras_learning_agent.agent.learn_signal import learn_signal
from libras_learning_agent.api.schemas import (
    AgentEventOut,
    CandidateDetail,
    CandidateSummary,
    ResearchRequest,
    ResearchResponse,
    SignalOut,
    SourceOut,
    ValidationRequest,
)
from libras_learning_agent.database.db import get_db
from libras_learning_agent.database.models import AgentEvent, Signal, SignalSource, Source
from libras_learning_agent.research import SourceComparisonError, WebSearchError

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


app.include_router(router)

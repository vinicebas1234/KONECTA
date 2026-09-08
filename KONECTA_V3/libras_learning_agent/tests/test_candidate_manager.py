"""Testes reais do Ciclo 2 (Candidate Manager) do Libras Learning Agent.

Nada aqui é simulado: sobe um SQLite temporário de verdade por teste (mesmo
padrão de `test_foundation.py`/`test_vision_hand_landmarks.py`) e faz
commits/queries reais via SQLAlchemy — sem mocks.

O teste mais importante do arquivo é `test_illegal_transition_raises_and_writes_nothing`:
é o desenhado para pegar uma transição de status que pule validação e treino
inteiros (ex. DISCOVERED direto pra PRODUCTION). Ver o relatório do Ciclo 2
para a prova por reversão manual (comentar a checagem, rodar, ver falhar,
desfazer).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from libras_learning_agent.agent.candidate_manager import (
    IllegalTransitionError,
    advance_status,
    create_signal_candidate,
    get_signal,
    list_signals_by_status,
    register_validation,
)
from libras_learning_agent.database.db import Base
from libras_learning_agent.database.models import AgentEvent, Signal, Validation


def _sqlite_url(path: Path) -> str:
    return "sqlite:///" + str(path).replace("\\", "/")


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine(_sqlite_url(tmp_path / "candidate_manager.db"), connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


def _count(session: Session, model) -> int:
    return len(session.scalars(select(model)).all())


def _to_validation_required(session: Session, concept: str) -> Signal:
    """Atalho: cria um sinal e avança até VALIDATION_REQUIRED (usado por vários testes)."""
    signal = create_signal_candidate(session, concept)
    advance_status(session, signal, "ANALYZING")
    advance_status(session, signal, "CANDIDATE")
    advance_status(session, signal, "VALIDATION_REQUIRED")
    return signal


# --------------------------------------------------------------------- 1 ---


def test_happy_path_full_flow_records_event_per_transition(session: Session) -> None:
    signal = create_signal_candidate(session, "ABACAXI", category="fruta")
    assert signal.status == "DISCOVERED"

    advance_status(session, signal, "ANALYZING")
    advance_status(session, signal, "CANDIDATE")
    advance_status(session, signal, "VALIDATION_REQUIRED")
    register_validation(session, signal, "approved", "vinicius")
    assert signal.status == "VALIDATED"

    # continua o caminho inteiro até PRODUCTION — prova que a tabela cobre o
    # fluxo completo sem levantar IllegalTransitionError em nenhum passo.
    advance_status(session, signal, "TRAINING")
    advance_status(session, signal, "EVALUATED")
    advance_status(session, signal, "PRODUCTION")
    assert signal.status == "PRODUCTION"

    # único sinal criado neste teste: todo AgentEvent da tabela pertence a ele.
    events = session.scalars(select(AgentEvent)).all()
    assert all(e.payload["signal_id"] == signal.id for e in events)
    # 8 transições no total: criação + 7 avanços de status.
    assert len(events) == 8

    event_types_in_order = [e.event_type for e in sorted(events, key=lambda e: e.timestamp)]
    assert event_types_in_order == [
        "candidate_created",
        "research_started",
        "research_completed",
        "validation_requested",
        "validation_completed",
        "training_started",
        "training_completed",
        "model_promoted",
    ]

    last_event = max(events, key=lambda e: e.timestamp)
    assert last_event.payload["from_status"] == "EVALUATED"
    assert last_event.payload["to_status"] == "PRODUCTION"

    # get_signal / list_signals_by_status também funcionam sobre o resultado.
    assert get_signal(session, signal.id).status == "PRODUCTION"
    assert signal.id in {s.id for s in list_signals_by_status(session, "PRODUCTION")}


# --------------------------------------------------------------------- 2 ---


def test_illegal_transition_raises_and_writes_nothing(session: Session) -> None:
    """O teste mais importante do ciclo — ver docstring do módulo."""
    signal = create_signal_candidate(session, "BANANA")
    events_before = _count(session, AgentEvent)
    status_before = signal.status

    with pytest.raises(IllegalTransitionError):
        advance_status(session, signal, "PRODUCTION")  # pula validação e treino inteiros

    assert signal.status == status_before, "signal.status mudou mesmo com transição ilegal"
    assert _count(session, AgentEvent) == events_before, "um evento foi gravado para uma transição ilegal"

    # confirma também contra o banco (não só o objeto Python em memória).
    reloaded = get_signal(session, signal.id)
    assert reloaded.status == status_before


# --------------------------------------------------------------------- 3 ---


def test_register_validation_covers_all_four_decisions(session: Session) -> None:
    approved_signal = _to_validation_required(session, "APROVADO")
    register_validation(session, approved_signal, "approved", "vinicius")
    assert approved_signal.status == "VALIDATED"

    rejected_signal = _to_validation_required(session, "REJEITADO")
    register_validation(session, rejected_signal, "rejected", "vinicius")
    assert rejected_signal.status == "REJECTED"
    # REJECTED é terminal: qualquer nova transição precisa falhar.
    with pytest.raises(IllegalTransitionError):
        advance_status(session, rejected_signal, "ANALYZING")

    corrected_signal = _to_validation_required(session, "CORRIGIR")
    register_validation(session, corrected_signal, "corrected", "vinicius")
    assert corrected_signal.status == "CANDIDATE"

    needs_review_signal = _to_validation_required(session, "REVISAR")
    register_validation(session, needs_review_signal, "needs_review", "vinicius")
    assert needs_review_signal.status == "CANDIDATE"


# --------------------------------------------------------------------- 4 ---


def test_register_validation_invalid_decision_raises_in_python_before_db(session: Session) -> None:
    signal = _to_validation_required(session, "DUVIDOSO")
    validations_before = _count(session, Validation)

    with pytest.raises(ValueError):
        register_validation(session, signal, "talvez", "vinicius")

    assert _count(session, Validation) == validations_before, "uma Validation foi gravada com decision inválida"
    assert signal.status == "VALIDATION_REQUIRED", "status mudou mesmo com decision inválida"

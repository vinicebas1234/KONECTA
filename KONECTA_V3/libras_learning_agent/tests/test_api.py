"""Testes reais do Ciclo 6 (API HTTP) do Libras Learning Agent.

Mesmo espírito dos ciclos anteriores: SQLite temporário real por teste, sem
mock de banco (`TestClient` sobe o `app` de verdade, em processo). Os testes
de listagem/detalhe/validação criam o `Signal` direto via
`candidate_manager` (sem passar por `learn_signal`) para não gastar cota do
Gemini — só `test_research_real_end_to_end` gasta cota de verdade, e só roda
se `GEMINI_API_KEY` estiver configurada (mesmo padrão de
`test_learn_signal.py`). `test_research_external_failure_returns_502` prova
o mapeamento pra 502 via monkeypatch, independente da cota real.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from libras_learning_agent.agent.candidate_manager import (
    advance_status,
    create_signal_candidate,
)
from libras_learning_agent.database.models import Signal
import libras_learning_agent.api.app as api_app_module
from libras_learning_agent.api.app import app, get_session
from libras_learning_agent.core.config import get_settings
from libras_learning_agent.database.db import Base
from libras_learning_agent.database.models import SignalSource, Source
from libras_learning_agent.research import WebSearchError


def _sqlite_url(path: Path) -> str:
    return "sqlite:///" + str(path).replace("\\", "/")


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine(_sqlite_url(tmp_path / "api.db"), connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


@pytest.fixture
def client(session: Session):
    """`TestClient` com `get_session` sobrescrito pra usar o SQLite temporário do teste
    (mesma sessão que o corpo do teste manipula direto), em vez do banco real do LLA.
    """

    def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _to_validation_required(session: Session, concept: str) -> Signal:
    signal = create_signal_candidate(session, concept)
    advance_status(session, signal, "ANALYZING")
    advance_status(session, signal, "CANDIDATE")
    advance_status(session, signal, "VALIDATION_REQUIRED")
    return signal


# --------------------------------------------------------------------- 1 ---


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# --------------------------------------------------------------------- 2 ---


def test_list_and_get_candidate_include_sources_and_events(session: Session, client: TestClient) -> None:
    signal = _to_validation_required(session, "ABACAXI")

    source = Source(url="https://example.com/abacaxi", title="Abacaxi - dicionário")
    session.add(source)
    session.flush()
    session.add(SignalSource(signal_id=signal.id, source_id=source.id))
    session.commit()

    list_response = client.get("/api/libras/candidates")
    assert list_response.status_code == 200
    ids = [item["id"] for item in list_response.json()]
    assert signal.id in ids

    filtered = client.get("/api/libras/candidates", params={"status": "VALIDATION_REQUIRED"})
    assert filtered.status_code == 200
    assert all(item["status"] == "VALIDATION_REQUIRED" for item in filtered.json())

    detail_response = client.get(f"/api/libras/candidates/{signal.id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["concept"] == "ABACAXI"
    assert detail["status"] == "VALIDATION_REQUIRED"
    assert len(detail["sources"]) == 1
    assert detail["sources"][0]["url"] == "https://example.com/abacaxi"

    event_types = [e["event_type"] for e in detail["events"]]
    assert event_types == [
        "candidate_created",
        "research_started",
        "research_completed",
        "validation_requested",
    ]
    timestamps = [e["timestamp"] for e in detail["events"]]
    assert timestamps == sorted(timestamps), "eventos não vieram em ordem cronológica"


def test_get_candidate_not_found_returns_404(client: TestClient) -> None:
    response = client.get("/api/libras/candidates/does-not-exist")
    assert response.status_code == 404


# --------------------------------------------------------------------- 3 ---


@pytest.mark.parametrize(
    "decision,expected_status",
    [
        ("approved", "VALIDATED"),
        ("rejected", "REJECTED"),
        ("corrected", "CANDIDATE"),
        ("needs_review", "CANDIDATE"),
    ],
)
def test_validation_endpoint_covers_the_four_decisions(
    session: Session, client: TestClient, decision: str, expected_status: str
) -> None:
    signal = _to_validation_required(session, f"CONCEITO-{decision}")
    response = client.post(
        f"/api/libras/candidates/{signal.id}/validation",
        json={"decision": decision, "validator": "vinicius", "notes": None},
    )
    assert response.status_code == 200
    assert response.json()["status"] == expected_status


def test_validation_invalid_decision_returns_400(session: Session, client: TestClient) -> None:
    signal = _to_validation_required(session, "CONCEITO-INVALIDO")
    response = client.post(
        f"/api/libras/candidates/{signal.id}/validation",
        json={"decision": "not_a_real_decision", "validator": "vinicius"},
    )
    assert response.status_code == 400


def test_validation_illegal_transition_returns_409(session: Session, client: TestClient) -> None:
    # sinal ainda em DISCOVERED — validar antes da hora é transição ilegal.
    signal = create_signal_candidate(session, "CONCEITO-CEDO-DEMAIS")
    response = client.post(
        f"/api/libras/candidates/{signal.id}/validation",
        json={"decision": "approved", "validator": "vinicius"},
    )
    assert response.status_code == 409
    assert "detail" in response.json()


def test_validation_not_found_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/libras/candidates/does-not-exist/validation",
        json={"decision": "approved", "validator": "vinicius"},
    )
    assert response.status_code == 404


# --------------------------------------------------------------------- 4 ---


@pytest.mark.skipif(
    not get_settings().gemini_api_key,
    reason="GEMINI_API_KEY não configurada no ambiente — ver instruções do Ciclo 4",
)
def test_research_real_end_to_end(client: TestClient) -> None:
    response = client.post("/api/libras/research", json={"concept": "computador", "max_results": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["concept"] == "computador"
    assert body["status"] == "VALIDATION_REQUIRED"
    assert body["classification"] is not None
    assert body["sources_count"] and body["sources_count"] > 0


def test_research_external_failure_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prova o mapeamento WebSearchError -> 502 sem depender da cota real do Gemini."""

    def _boom(*args, **kwargs):
        raise WebSearchError("erro simulado de busca (monkeypatch)")

    monkeypatch.setattr(api_app_module, "learn_signal", _boom)

    response = client.post("/api/libras/research", json={"concept": "qualquer-coisa"})
    assert response.status_code == 502
    assert "erro simulado" in response.json()["detail"]

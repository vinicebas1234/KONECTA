"""Testes reais do Ciclo 8 (progresso/acurácia de modelos) do Libras Learning Agent.

Mesmo espírito de `test_api.py`: SQLite temporário real por teste, sem mock de
banco, `TestClient` sobe o `app` de verdade. `ModelVersion`/`TrainingRun` são
criados direto no banco (sem rodar `ml/training.py`) — não precisa processar
vídeo pra testar a API.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from libras_learning_agent.agent.candidate_manager import (
    LEGAL_TRANSITIONS,
    advance_status,
    create_signal_candidate,
)
from libras_learning_agent.api.app import app, get_session
from libras_learning_agent.database.db import Base
from libras_learning_agent.database.models import ModelVersion, TrainingRun


def _sqlite_url(path: Path) -> str:
    return "sqlite:///" + str(path).replace("\\", "/")


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine(_sqlite_url(tmp_path / "api_models.db"), connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


@pytest.fixture
def client(session: Session):
    def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_model(
    session: Session,
    *,
    version: str,
    status: str = "evaluated",
    dataset_version: str = "vlibrasil_subset_v1",
    metrics: dict | None = None,
    created_at: datetime | None = None,
) -> ModelVersion:
    model = ModelVersion(
        version=version,
        dataset_version=dataset_version,
        signals_count=3,
        metrics=metrics if metrics is not None else {"top1_accuracy": 0.8, "top5_accuracy": 0.95},
        status=status,
        file_path=f"./libras_learning_agent/models/{version}/references.npz",
    )
    if created_at is not None:
        model.created_at = created_at
    session.add(model)
    session.commit()
    session.refresh(model)
    return model


def _make_training_run(session: Session, *, dataset_version: str, metrics: dict | None = None) -> TrainingRun:
    run = TrainingRun(
        dataset_version=dataset_version,
        base_model="dtw_knn_prototype",
        status="completed",
        metrics=metrics or {"top1_accuracy": 0.8},
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


# --------------------------------------------------------------------- 1: listagem/detalhe ---


def test_list_models_returns_summary_ordered_by_created_at_desc(session: Session, client: TestClient) -> None:
    now = datetime.now(timezone.utc)
    older = _make_model(session, version="model_v001", created_at=now - timedelta(days=1))
    newer = _make_model(session, version="model_v002", created_at=now)

    response = client.get("/api/libras/models")
    assert response.status_code == 200
    body = response.json()
    ids = [m["id"] for m in body]
    assert ids == [newer.id, older.id]

    first = body[0]
    assert first["version"] == "model_v002"
    assert first["dataset_version"] == "vlibrasil_subset_v1"
    assert first["signals_count"] == 3
    assert first["status"] == "evaluated"
    assert first["top1_accuracy"] == 0.8
    assert first["top5_accuracy"] == 0.95
    # resumo não inclui o dict metrics inteiro nem file_path
    assert "metrics" not in first
    assert "file_path" not in first


def test_list_models_filters_by_status(session: Session, client: TestClient) -> None:
    _make_model(session, version="model_v001", status="evaluated")
    production = _make_model(session, version="model_v002", status="production")

    response = client.get("/api/libras/models", params={"status": "production"})
    assert response.status_code == 200
    body = response.json()
    assert [m["id"] for m in body] == [production.id]


def test_list_models_defensive_metrics_summary_missing_keys(session: Session, client: TestClient) -> None:
    # metrics de formato diferente (ciclo futuro) -- .get() defensivo, sem 500.
    model = _make_model(session, version="model_v003", metrics={"some_other_format": True})

    response = client.get("/api/libras/models")
    assert response.status_code == 200
    entry = next(m for m in response.json() if m["id"] == model.id)
    assert entry["top1_accuracy"] is None
    assert entry["top5_accuracy"] is None


def test_get_model_detail_includes_full_metrics_and_matching_training_runs(
    session: Session, client: TestClient
) -> None:
    metrics = {"top1_accuracy": 0.8, "top5_accuracy": 0.95, "per_signer": {"joao": {"top1_accuracy": 0.7}}}
    model = _make_model(session, version="model_v001", dataset_version="vlibrasil_subset_v1", metrics=metrics)
    run = _make_training_run(session, dataset_version="vlibrasil_subset_v1")
    # TrainingRun de outro dataset_version não deve aparecer
    _make_training_run(session, dataset_version="outro_dataset")

    response = client.get(f"/api/libras/models/{model.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["metrics"] == metrics
    assert body["file_path"] == model.file_path
    training_run_ids = [t["id"] for t in body["training_runs"]]
    assert training_run_ids == [run.id]


def test_get_model_not_found_returns_404(client: TestClient) -> None:
    response = client.get("/api/libras/models/does-not-exist")
    assert response.status_code == 404


# --------------------------------------------------------------------- 2: promote ---


def test_promote_evaluated_to_production_succeeds(session: Session, client: TestClient) -> None:
    model = _make_model(session, version="model_v001", status="evaluated")

    response = client.post(f"/api/libras/models/{model.id}/promote")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "production"
    assert body["demoted_model_id"] is None

    session.refresh(model)
    assert model.status == "production"


def test_promoting_second_model_demotes_first_to_archived(session: Session, client: TestClient) -> None:
    """A regra mais fácil de esquecer: só um ModelVersion "production" por vez."""
    first = _make_model(session, version="model_v001", status="evaluated")
    second = _make_model(session, version="model_v002", status="evaluated")

    first_promote = client.post(f"/api/libras/models/{first.id}/promote")
    assert first_promote.status_code == 200
    assert first_promote.json()["demoted_model_id"] is None

    second_promote = client.post(f"/api/libras/models/{second.id}/promote")
    assert second_promote.status_code == 200
    body = second_promote.json()
    assert body["status"] == "production"
    assert body["demoted_model_id"] == first.id

    session.refresh(first)
    session.refresh(second)
    assert first.status == "archived"
    assert second.status == "production"

    # confirma via GET /models que nunca há dois em "production" ao mesmo tempo
    listing = client.get("/api/libras/models").json()
    production_ids = [m["id"] for m in listing if m["status"] == "production"]
    assert production_ids == [second.id]


def test_promote_already_production_returns_409(session: Session, client: TestClient) -> None:
    model = _make_model(session, version="model_v001", status="production")
    response = client.post(f"/api/libras/models/{model.id}/promote")
    assert response.status_code == 409
    assert "detail" in response.json()


def test_promote_archived_returns_409(session: Session, client: TestClient) -> None:
    model = _make_model(session, version="model_v001", status="archived")
    response = client.post(f"/api/libras/models/{model.id}/promote")
    assert response.status_code == 409


def test_promote_not_found_returns_404(client: TestClient) -> None:
    response = client.post("/api/libras/models/does-not-exist/promote")
    assert response.status_code == 404


# --------------------------------------------------------------------- 3: rollback ---


def test_rollback_production_to_archived_succeeds(session: Session, client: TestClient) -> None:
    model = _make_model(session, version="model_v001", status="production")

    response = client.post(f"/api/libras/models/{model.id}/rollback")
    assert response.status_code == 200
    assert response.json()["status"] == "archived"

    session.refresh(model)
    assert model.status == "archived"


def test_rollback_non_production_returns_409(session: Session, client: TestClient) -> None:
    model = _make_model(session, version="model_v001", status="evaluated")
    response = client.post(f"/api/libras/models/{model.id}/rollback")
    assert response.status_code == 409
    assert "detail" in response.json()


def test_rollback_not_found_returns_404(client: TestClient) -> None:
    response = client.post("/api/libras/models/does-not-exist/rollback")
    assert response.status_code == 404


# --------------------------------------------------------------------- 4: stats ---


def test_stats_counts_signals_by_status_including_zero_for_untouched_statuses(
    session: Session, client: TestClient
) -> None:
    create_signal_candidate(session, "ABACAXI")  # DISCOVERED
    b = create_signal_candidate(session, "BANANA")
    advance_status(session, b, "ANALYZING")  # ANALYZING
    c = create_signal_candidate(session, "CASA")
    advance_status(session, c, "ANALYZING")
    advance_status(session, c, "CANDIDATE")  # CANDIDATE
    create_signal_candidate(session, "DINHEIRO")  # outro DISCOVERED

    response = client.get("/api/libras/stats")
    assert response.status_code == 200
    body = response.json()

    assert body["signals_by_status"]["DISCOVERED"] == 2
    assert body["signals_by_status"]["ANALYZING"] == 1
    assert body["signals_by_status"]["CANDIDATE"] == 1
    assert body["signals_total"] == 4

    # todos os 11 estados aparecem no JSON, mesmo com 0 sinais -- não fica ausente.
    assert set(body["signals_by_status"].keys()) == set(LEGAL_TRANSITIONS.keys())
    for status in LEGAL_TRANSITIONS:
        if status not in {"DISCOVERED", "ANALYZING", "CANDIDATE"}:
            assert body["signals_by_status"][status] == 0


def test_stats_counts_models_by_status(session: Session, client: TestClient) -> None:
    _make_model(session, version="model_v001", status="evaluated")
    _make_model(session, version="model_v002", status="evaluated")
    _make_model(session, version="model_v003", status="production")

    response = client.get("/api/libras/stats")
    assert response.status_code == 200
    body = response.json()

    assert body["models_by_status"]["evaluated"] == 2
    assert body["models_by_status"]["production"] == 1
    assert body["models_by_status"]["training"] == 0
    assert body["models_by_status"]["archived"] == 0
    assert body["models_total"] == 3

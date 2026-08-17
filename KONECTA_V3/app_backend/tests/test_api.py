"""API tests for the KONECTA backend.

Run from repo root:
    pytest app_backend/tests -v
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app_backend.tests.conftest import HEADERS

USER_ID = "11111111-1111-4111-8111-111111111111"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health_ok(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] is True
    assert "version" in body
    assert "uptime_seconds" in body
    assert isinstance(body.get("performance"), dict)


def test_legacy_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["health"] == "/api/health"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

def test_models_available_seeded(client: TestClient) -> None:
    r = client.get("/api/models/available")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    names = {m["name"] for m in body["items"]}
    assert "konecta_v3" in names


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_protected_requires_api_key(client: TestClient) -> None:
    for path, payload in [
        ("/api/metrics", {"name": "x", "value": 1}),
        (
            "/api/webhook/signal-recognized",
            {"user_id": USER_ID, "signal_label": "OLA", "confidence": 0.9},
        ),
    ]:
        r = client.post(path, json=payload)
        assert r.status_code == 401
        assert "API key" in r.json()["detail"]


def test_protected_rejects_bad_key(client: TestClient) -> None:
    r = client.post(
        "/api/metrics",
        json={"name": "x", "value": 1},
        headers={"X-API-Key": "wrong-key"},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def test_metrics_ingest(client: TestClient) -> None:
    r = client.post(
        "/api/metrics",
        json={"name": "inference_latency_ms", "value": 42.5, "tags": {"source": "n8n"}},
        headers=HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] is True
    assert body["name"] == "inference_latency_ms"
    assert body["value"] == 42.5


def test_metrics_validation(client: TestClient) -> None:
    r = client.post("/api/metrics", json={"value": 1}, headers=HEADERS)
    assert r.status_code == 422
    assert r.json()["detail"][0]["type"] == "missing"


# ---------------------------------------------------------------------------
# Webhook + signals
# ---------------------------------------------------------------------------

def test_webhook_records_signal(client: TestClient) -> None:
    r = client.post(
        "/api/webhook/signal-recognized",
        json={
            "user_id": USER_ID,
            "signal_label": "OLA",
            "confidence": 0.95,
            "latency_ms": 42,
            "model_used": "konecta_v3",
            "username": "maria",
        },
        headers=HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["signal_id"]
    assert body["user_id"] == USER_ID

    r = client.get("/api/signals", params={"user_id": USER_ID})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert body["items"][0]["signal_label"] == "OLA"
    assert body["items"][0]["confidence"] == 0.95


def test_webhook_rejects_invalid_confidence(client: TestClient) -> None:
    r = client.post(
        "/api/webhook/signal-recognized",
        json={"user_id": USER_ID, "signal_label": "X", "confidence": 2.0},
        headers=HEADERS,
    )
    assert r.status_code == 422


def test_signals_pagination(client: TestClient) -> None:
    r = client.get("/api/signals", params={"page": 1, "page_size": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert len(body["items"]) <= 1


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------

def test_prometheus_metrics_endpoint(client: TestClient) -> None:
    client.get("/api/health")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert "konecta_http_requests_total" in r.text
    assert "konecta_http_request_duration_seconds" in r.text


def test_404_returns_json_error(client: TestClient) -> None:
    r = client.get("/api/nonexistent")
    assert r.status_code == 404
    assert "detail" in r.json()

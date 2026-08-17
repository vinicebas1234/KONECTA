"""Test fixtures for the KONECTA backend.

Env vars are set BEFORE importing app_backend so the cached Settings object
uses an isolated temp SQLite DB and a known API key.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_TMP_DB = Path(tempfile.mkdtemp(prefix="konecta_tests_")) / "test.db"
os.environ["KONECTA_API_KEY"] = "test-api-key"
os.environ["RATE_LIMIT"] = "1000/minute"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.as_posix()}"
os.environ["LOG_JSON"] = "false"
os.environ["ENVIRONMENT"] = "test"
os.environ["PROMETHEUS_ENABLED"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app_backend.main import app  # noqa: E402

TEST_KEY = "test-api-key"
HEADERS = {"X-API-Key": TEST_KEY}


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as c:
        yield c

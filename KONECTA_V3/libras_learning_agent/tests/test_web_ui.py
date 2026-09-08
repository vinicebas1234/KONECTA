"""Ciclo 10 do Libras Learning Agent: UI estática da fila de validação.

Não testa o JS em si (sem browser headless na suíte — a verificação visual
real foi feita manualmente, ver relatório do ciclo). Só prova o que um teste
automatizado consegue provar sem mock: o `StaticFiles(html=True)` monta
`index.html` de verdade em "/" via TestClient, e o mount não quebra nenhuma
rota de API já existente (regressão real).

Mesmo padrão de fixtures de `tests/test_api.py`: SQLite temporário real por
teste (não o banco de dados real/não-inicializado do LLA), `get_session`
sobrescrito via `app.dependency_overrides` — não é mock de ORM, é isolamento
de banco entre testes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from libras_learning_agent.api.app import app, get_session
from libras_learning_agent.database.db import Base


def _sqlite_url(path: Path) -> str:
    return "sqlite:///" + str(path).replace("\\", "/")


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine(_sqlite_url(tmp_path / "web_ui.db"), connect_args={"check_same_thread": False})
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


def test_root_serves_the_real_index_html(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Libras Learning Agent" in response.text
    assert 'id="view"' in response.text


def test_static_assets_are_served(client: TestClient) -> None:
    js = client.get("/app.js")
    css = client.get("/styles.css")

    assert js.status_code == 200
    assert "javascript" in js.headers["content-type"]
    assert css.status_code == 200
    assert "text/css" in css.headers["content-type"]


def test_static_mount_does_not_shadow_existing_api_routes(client: TestClient) -> None:
    """Regressão: /health e /api/libras/candidates continuam respondendo como
    antes do mount de "/" ser adicionado — prova que o Mount coringa não
    intercepta rotas mais específicas registradas antes dele.
    """
    health = client.get("/health")
    candidates = client.get("/api/libras/candidates")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    assert candidates.status_code == 200
    assert candidates.json() == []


def test_unknown_path_returns_404_not_index_html(client: TestClient) -> None:
    # html=True do StaticFiles só cobre "/" (index.html) e arquivos que
    # existem de fato — um caminho desconhecido continua 404, não vaza o
    # index.html pra qualquer rota digitada errada.
    response = client.get("/isto-nao-existe")

    assert response.status_code == 404

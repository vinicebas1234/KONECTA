"""Smoke test da API FastAPI (REST + WebSocket) com a fonte sintetica.

Rodar: `python tests/test_api_smoke.py` (com fastapi/httpx instalados).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from backend.main import app


def main() -> None:
    client = TestClient(app)

    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"

    r = client.get("/api/fontes")
    assert r.status_code == 200
    fontes = r.json()["fontes"]
    assert fontes["sintetico"] is True
    print(f"Fontes disponiveis: {fontes}")

    # Antes de qualquer analise, GET /api/analise deve dar 404
    # (estado limpo — este teste roda em processo proprio)
    r = client.get("/api/analise")
    assert r.status_code == 404

    # WebSocket com progresso em tempo real
    progresso = []
    with client.websocket_connect("/ws/analise") as ws:
        ws.send_json({"fonte": "sintetico"})
        while True:
            msg = ws.receive_json()
            if msg["tipo"] == "progresso":
                progresso.append(msg["mensagem"])
            elif msg["tipo"] == "concluido":
                analise = msg["analise"]
                break
            else:
                raise AssertionError(f"erro no WS: {msg}")
    assert len(progresso) >= 5, f"esperava mensagens de progresso, veio {progresso}"
    assert analise["estatisticas"]["n_sinais"] == 5
    print(f"Progresso WS ({len(progresso)} etapas): {progresso[:3]}...")

    # Depois da analise via WS, o REST serve o resultado em cache
    r = client.get("/api/analise")
    assert r.status_code == 200
    assert r.json()["estatisticas"]["n_amostras"] == analise["estatisticas"]["n_amostras"]

    r = client.get("/api/analise/relatorio")
    assert r.status_code == 200 and "Relatorio do Knowledge Engine" in r.text

    # POST sincrono tambem funciona
    r = client.post("/api/analise", params={"fonte": "sintetico"})
    assert r.status_code == 200

    print("OK — API smoke test passou.")


if __name__ == "__main__":
    main()

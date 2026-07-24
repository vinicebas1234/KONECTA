"""Aplicacao FastAPI do KONECTA V2.

Executar a partir da pasta KONECTA_V2:
    .venv\\Scripts\\uvicorn backend.main:app --reload --port 8000

Ou de qualquer lugar:
    uvicorn backend.main:app --app-dir C:/KONECTA/KONECTA_V2 --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.api.ws import router as ws_router

app = FastAPI(
    title="KONECTA V2 API",
    description="Plataforma de pesquisa em reconhecimento de Libras — Knowledge Engine",
    version="0.1.0",
)

# Em desenvolvimento o frontend (Vite, porta 5173) acessa via proxy ou direto.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(ws_router)

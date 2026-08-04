"""SIGNLAB — Laboratório Visual de Treinamento e Reconhecimento de Libras.

Execução:
    python -m uvicorn app.backend.main:app --port 8100
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .database import init_db
from .storage import PROJECTS_DIR
from .routes import projects, classes, examples, training

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    PROJECTS_DIR.mkdir(exist_ok=True)
    yield


app = FastAPI(title="SIGNLAB", version="1.0.0", lifespan=lifespan)

app.include_router(projects.router)
app.include_router(classes.router)
app.include_router(examples.router)
app.include_router(training.router)

app.mount("/files", StaticFiles(directory=PROJECTS_DIR, check_dir=False), name="files")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

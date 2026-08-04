"""Organização dos arquivos de projeto no filesystem.

Layout (por projeto, conforme especificação):

projects/<slug>/
├── images/<classe>/      exemplos de imagem
├── videos/<classe>/      exemplos de vídeo
├── landmarks/            (fase 2+)
├── sequences/            (fase 3+)
├── augmented/            (fase 4+)
├── models/               (fase 2+)
├── experiments/          (fase 5+)
└── reports/              (fase 5+)
"""
import re
import shutil
import unicodedata
import uuid
from pathlib import Path

from .database import ROOT

PROJECTS_DIR = ROOT / "projects"

PROJECT_SUBDIRS = [
    "images", "videos", "landmarks", "sequences",
    "augmented", "models", "experiments", "reports",
]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


def slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "item"


def kind_for(filename: str) -> str | None:
    ext = Path(filename).suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    return None


def create_project_dirs(project_slug: str) -> Path:
    base = PROJECTS_DIR / project_slug
    for sub in PROJECT_SUBDIRS:
        (base / sub).mkdir(parents=True, exist_ok=True)
    return base


def example_dir(project_slug: str, class_slug: str, kind: str) -> Path:
    sub = "images" if kind == "image" else "videos"
    path = PROJECTS_DIR / project_slug / sub / class_slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_example(project_slug: str, class_slug: str, kind: str,
                 filename: str, data: bytes) -> tuple[str, str]:
    """Grava o arquivo e retorna (nome_final, caminho_relativo_a_projects)."""
    safe_name = f"{uuid.uuid4().hex[:8]}_{slugify(Path(filename).stem)}{Path(filename).suffix.lower()}"
    dest = example_dir(project_slug, class_slug, kind) / safe_name
    dest.write_bytes(data)
    return safe_name, dest.relative_to(PROJECTS_DIR).as_posix()


def delete_file(rel_path: str) -> None:
    path = PROJECTS_DIR / rel_path
    if path.is_file():
        path.unlink()


def delete_class_files(project_slug: str, class_slug: str) -> None:
    for sub in ("images", "videos"):
        path = PROJECTS_DIR / project_slug / sub / class_slug
        if path.is_dir():
            shutil.rmtree(path)


def delete_project_files(project_slug: str) -> None:
    path = PROJECTS_DIR / project_slug
    if path.is_dir():
        shutil.rmtree(path)

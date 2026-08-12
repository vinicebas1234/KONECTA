"""Conexão SQLite e schema do SIGNLAB.

Metadados (projetos, classes, exemplos) ficam no SQLite;
arquivos grandes (imagens, vídeos) ficam no filesystem em projects/.
"""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "signlab.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS classes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    position    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (project_id, slug)
);

CREATE TABLE IF NOT EXISTS examples (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id    INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL CHECK (kind IN ('image', 'video')),
    source      TEXT NOT NULL DEFAULT 'upload' CHECK (source IN ('upload', 'webcam')),
    filename    TEXT NOT NULL,
    rel_path    TEXT NOT NULL,
    size_bytes  INTEGER NOT NULL DEFAULT 0,
    signer_name TEXT DEFAULT 'unknown',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS experiments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    model_type      TEXT NOT NULL,
    metrics         TEXT,
    classes         TEXT,
    feature_config  TEXT,
    model_path      TEXT,
    cross_signer    TEXT DEFAULT 'normal',
    train_signers   TEXT,
    test_signer     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS signer_splits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    signer_name     TEXT NOT NULL,
    split           TEXT CHECK (split IN ('train', 'test')),
    UNIQUE (project_id, signer_name, split)
);

CREATE INDEX IF NOT EXISTS idx_classes_project ON classes(project_id);
CREATE INDEX IF NOT EXISTS idx_examples_class ON examples(class_id);
CREATE INDEX IF NOT EXISTS idx_experiments_project ON experiments(project_id);
"""


def init_db() -> None:
    con = sqlite3.connect(DB_PATH)
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def get_db():
    """Dependency do FastAPI: uma conexão por request.

    check_same_thread=False é seguro aqui porque a conexão não é
    compartilhada entre requests — mas o FastAPI pode executar a
    dependency e o endpoint em threads diferentes.
    """
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()

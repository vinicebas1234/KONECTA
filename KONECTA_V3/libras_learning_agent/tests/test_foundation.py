"""Testes reais do Ciclo 0 (fundação) do Libras Learning Agent.

Nada aqui é simulado: sobem SQLite temporário de verdade, rodam
`alembic upgrade head` de verdade (subprocess) e inserem/leem linhas reais
via SQLAlchemy. Rodar de dentro da venv própria do LLA — ver o relatório do
Ciclo 0 para o comando exato usado.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

PACKAGE_DIR = Path(__file__).resolve().parents[1]  # libras_learning_agent/
REPO_ROOT = PACKAGE_DIR.parent  # KONECTA_V3/
ALEMBIC_INI = PACKAGE_DIR / "database" / "migrations" / "alembic.ini"

EXPECTED_TABLES = {
    "sources",
    "videos",
    "signals",
    "signal_variants",
    "landmark_samples",
    "validations",
    "training_runs",
    "model_versions",
    "agent_tasks",
    "agent_events",
}


def _sqlite_url(path: Path) -> str:
    return "sqlite:///" + str(path).replace("\\", "/")


def _run_alembic_upgrade(db_path: Path) -> None:
    env = os.environ.copy()
    env["LLA_DATABASE_URL"] = _sqlite_url(db_path)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), "upgrade", "head"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"alembic upgrade head falhou:\nstdout={result.stdout}\nstderr={result.stderr}"
    )


def test_alembic_upgrade_creates_all_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "alembic_test.db"
    _run_alembic_upgrade(db_path)

    assert db_path.exists()
    engine = create_engine(_sqlite_url(db_path))
    try:
        tables = set(inspect(engine).get_table_names())
        missing = EXPECTED_TABLES - tables
        assert not missing, f"tabelas faltando após alembic upgrade head: {missing}"
    finally:
        engine.dispose()


def test_insert_and_read_row_in_every_table_with_valid_fks(tmp_path: Path) -> None:
    db_path = tmp_path / "crud_test.db"
    _run_alembic_upgrade(db_path)

    engine = create_engine(_sqlite_url(db_path), connect_args={"check_same_thread": False})
    now = datetime.now(timezone.utc).isoformat()
    metrics_json = json.dumps({"accuracy": 0.9})

    try:
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))

            conn.execute(
                text(
                    "INSERT INTO sources (id, url, title, author, publisher, source_type, "
                    "license, retrieved_at, reliability_score, usage_notes) VALUES "
                    "('src1', 'https://example.org', 'Dicionario X', 'Autor', 'Editora', "
                    "'dictionary', 'CC-BY', :now, 0.9, 'nota')"
                ),
                {"now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO videos (id, source_id, url_or_path, title, duration, fps, "
                    "width, height, license, processing_status, quality_score) VALUES "
                    "('vid1', 'src1', 'https://example.org/v.mp4', 'Video X', 12.5, 30.0, "
                    "640, 480, 'CC-BY', 'processed', 0.8)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO signals (id, concept, category, description, status, "
                    "confidence, created_at, updated_at) VALUES "
                    "('sig1', 'ABACAXI', 'fruta', 'sinal de abacaxi', 'CANDIDATE', 0.7, :now, :now)"
                ),
                {"now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO signal_variants (id, signal_id, name, description, region, "
                    "context, confidence, status) VALUES "
                    "('var1', 'sig1', 'ABACAXI-SP', 'variante SP', 'SP', 'informal', 0.6, 'CANDIDATE')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO landmark_samples (id, signal_id, variant_id, video_id, "
                    "file_path, frame_count, fps, quality_score, created_at) VALUES "
                    "('lm1', 'sig1', 'var1', 'vid1', './data/landmarks/lm1.npy', 45, 30.0, 0.85, :now)"
                ),
                {"now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO validations (id, signal_id, decision, validator, notes, timestamp) "
                    "VALUES ('val1', 'sig1', 'approved', 'vinicius', 'ok', :now)"
                ),
                {"now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO training_runs (id, dataset_version, base_model, status, "
                    "started_at, completed_at, metrics) VALUES "
                    "('run1', 'ds_v1', 'mediapipe_v1', 'completed', :now, :now, :metrics)"
                ),
                {"now": now, "metrics": metrics_json},
            )
            conn.execute(
                text(
                    "INSERT INTO model_versions (id, version, dataset_version, signals_count, "
                    "metrics, status, created_at, file_path) VALUES "
                    "('mv1', 'model_v001', 'ds_v1', 1, :metrics, 'evaluated', :now, "
                    "'./libras_learning_agent/models/model_v001.joblib')"
                ),
                {"now": now, "metrics": metrics_json},
            )
            conn.execute(
                text(
                    "INSERT INTO agent_tasks (id, task_id, type, related_signal, status, "
                    "created_at, completed_at, error) VALUES "
                    "('task1', 'task-abc', 'extract_landmarks', 'ABACAXI', 'completed', :now, :now, NULL)"
                ),
                {"now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO agent_events (id, event_type, payload, timestamp) VALUES "
                    "('evt1', 'landmarks_extracted', :payload, :now)"
                ),
                {"now": now, "payload": json.dumps({"signal_id": "sig1"})},
            )

        with engine.connect() as conn:
            for table in EXPECTED_TABLES:
                row = conn.execute(text(f"SELECT * FROM {table}")).fetchone()
                assert row is not None, f"tabela {table} está vazia após insert"

            # Prova que as FKs são de verdade válidas e resolvem via JOIN.
            joined = conn.execute(
                text(
                    "SELECT s.concept, v.name, ls.file_path, val.decision "
                    "FROM landmark_samples ls "
                    "JOIN signals s ON s.id = ls.signal_id "
                    "JOIN signal_variants v ON v.id = ls.variant_id "
                    "JOIN videos vid ON vid.id = ls.video_id "
                    "JOIN validations val ON val.signal_id = s.id"
                )
            ).fetchone()
            assert joined is not None
            assert joined[0] == "ABACAXI"
            assert joined[3] == "approved"
    finally:
        engine.dispose()


def test_isolation_defaults_do_not_point_to_shared_locations() -> None:
    """O teste de isolamento mais importante do ciclo.

    Precisa FALHAR se alguém trocar o default de `models_dir`/`database_url`
    para dentro do `KONECTA_V3/models/` compartilhado (auto-discovery de
    modelos de produção) ou para o banco do `app_backend`.
    """
    from libras_learning_agent.core.config import Settings

    settings = Settings(_env_file=None)

    models_dir_norm = Path(settings.models_dir).as_posix().strip("./")
    db_url = settings.database_url

    assert models_dir_norm.startswith("libras_learning_agent/"), (
        f"models_dir não está isolado sob libras_learning_agent/: {settings.models_dir!r}"
    )
    assert not models_dir_norm.startswith("models/") and models_dir_norm != "models", (
        f"models_dir aponta para o diretório compartilhado KONECTA_V3/models/: {settings.models_dir!r}"
    )
    assert "libras_learning_agent" in db_url, f"database_url não está isolado: {db_url!r}"
    assert "konecta.db" not in db_url, f"database_url aponta para o banco do app_backend: {db_url!r}"
    assert "app_backend" not in db_url, f"database_url aponta para dentro de app_backend/: {db_url!r}"


def test_settings_repr_masks_anthropic_api_key() -> None:
    from libras_learning_agent.core.config import Settings

    secret = "sk-ant-api03-thisistotallysecret1234567890"
    settings = Settings(_env_file=None, anthropic_api_key=secret)

    assert secret not in repr(settings)
    assert secret not in str(settings)
    assert secret not in json.dumps(settings.model_dump())
    # o valor real continua acessível diretamente pelo atributo — só a
    # serialização/representação é que mascara.
    assert settings.anthropic_api_key == secret


def test_settings_repr_masks_gemini_api_key() -> None:
    """Mesmo teste acima, para `gemini_api_key` (Ciclo 4) — mesmo padrão de mascaramento."""
    from libras_learning_agent.core.config import Settings

    secret = "AIzaSyThisIsTotallyASecretFakeGeminiKey123456"
    settings = Settings(_env_file=None, gemini_api_key=secret)

    assert secret not in repr(settings)
    assert secret not in str(settings)
    assert secret not in json.dumps(settings.model_dump())
    assert settings.gemini_api_key == secret


def test_logging_never_leaks_anthropic_api_key(tmp_path: Path) -> None:
    from libras_learning_agent.core.config import Settings
    from libras_learning_agent.core.logging_setup import configure_logging

    secret = "sk-ant-api03-thisistotallysecret1234567890"
    settings = Settings(
        _env_file=None,
        anthropic_api_key=secret,
        log_dir=str(tmp_path / "logs"),
    )

    logger = configure_logging(settings)
    # Cenário 1: alguém loga o Settings inteiro (repr) por engano.
    logger.info(
        "configuração carregada", extra={"event": "config_loaded", "settings_repr": repr(settings)}
    )
    # Cenário 2: alguém loga a chave crua, sem passar por Settings.
    logger.info("chave usada: %s", secret, extra={"event": "debug_leak_attempt"})

    for handler in logger.handlers:
        handler.flush()

    log_path = Path(settings.log_dir) / "agent.log"
    content = log_path.read_text(encoding="utf-8")

    assert secret not in content, "a chave da API vazou em texto puro no log"
    assert "config_loaded" in content
    assert "debug_leak_attempt" in content

    for line in content.splitlines():
        record = json.loads(line)
        assert {"timestamp", "level", "event", "message"} <= record.keys()

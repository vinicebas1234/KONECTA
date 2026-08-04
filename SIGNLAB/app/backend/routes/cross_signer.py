"""Cross-signer evaluation: train on subset of signers, test on held-out signer."""
import json
import sqlite3
from fastapi import APIRouter, Depends
from app.backend.database import get_db

router = APIRouter()


@router.get("/projects/{project_id}/signers")
def list_signers(project_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Lista articuladores (signers) únicos do projeto."""
    rows = db.execute("""
        SELECT DISTINCT signer_name FROM examples
        JOIN classes ON examples.class_id = classes.id
        WHERE classes.project_id = ?
        ORDER BY signer_name
    """, (project_id,)).fetchall()
    return [row[0] for row in rows]


@router.post("/projects/{project_id}/cross-signer-split")
def set_cross_signer_split(
    project_id: int,
    body: dict,  # {"test_signer": "articulador_1"}
    db: sqlite3.Connection = Depends(get_db)
):
    """Define qual articulador é usado para teste (leave-one-out)."""
    test_signer = body.get("test_signer")
    if not test_signer:
        raise ValueError("test_signer é obrigatório")

    signers = db.execute("""
        SELECT DISTINCT signer_name FROM examples
        JOIN classes ON examples.class_id = classes.id
        WHERE classes.project_id = ?
    """, (project_id,)).fetchall()

    all_signers = [s[0] for s in signers]
    if test_signer not in all_signers:
        raise ValueError(f"Articulador '{test_signer}' não encontrado")

    train_signers = [s for s in all_signers if s != test_signer]

    db.execute("DELETE FROM signer_splits WHERE project_id = ?", (project_id,))
    for signer in train_signers:
        db.execute(
            "INSERT INTO signer_splits (project_id, signer_name, split) VALUES (?, ?, ?)",
            (project_id, signer, "train")
        )
    db.execute(
        "INSERT INTO signer_splits (project_id, signer_name, split) VALUES (?, ?, ?)",
        (project_id, test_signer, "test")
    )

    return {"train_signers": train_signers, "test_signer": test_signer}


@router.get("/projects/{project_id}/cross-signer-status")
def get_cross_signer_status(project_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Status do split cross-signer atual."""
    rows = db.execute("""
        SELECT signer_name, split FROM signer_splits
        WHERE project_id = ?
        ORDER BY signer_name
    """, (project_id,)).fetchall()

    if not rows:
        return {"configured": False}

    train_signers = [r[0] for r in rows if r[1] == "train"]
    test_signer = next((r[0] for r in rows if r[1] == "test"), None)

    return {
        "configured": True,
        "train_signers": train_signers,
        "test_signer": test_signer,
    }


@router.get("/projects/{project_id}/experiments-by-signer")
def list_experiments_by_signer(project_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Agrupa experimentos por configuração de signers para cross-signer."""
    rows = db.execute("""
        SELECT id, model_type, metrics, cross_signer, train_signers, test_signer, created_at
        FROM experiments
        WHERE project_id = ?
        AND cross_signer = 'cross_signer'
        ORDER BY created_at DESC
    """, (project_id,)).fetchall()

    result = []
    for row in rows:
        exp_id, model_type, metrics_json, cross_signer, train_signers_json, test_signer, created_at = row
        try:
            metrics = json.loads(metrics_json) if metrics_json else {}
        except:
            metrics = {}

        train_signers = json.loads(train_signers_json) if train_signers_json else []

        result.append({
            "id": exp_id,
            "model_type": model_type,
            "metrics": metrics,
            "train_signers": train_signers,
            "test_signer": test_signer,
            "created_at": created_at,
        })

    return result

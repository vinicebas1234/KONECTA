"""Treinamento, experimentos, predição e exportação (Fase 2 — imagens).

O treinamento roda em uma thread de background por projeto; o frontend
acompanha via polling em /train/status. Landmarks extraídos são cacheados
em projects/<slug>/landmarks/<example_id>.json para não reprocessar.
"""
import json
import sqlite3
import threading
import zipfile
from pathlib import Path

import joblib
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..database import DB_PATH, get_db
from ..storage import PROJECTS_DIR
from .projects import project_row

router = APIRouter(prefix="/api", tags=["training"])

JOBS: dict[int, dict] = {}          # project_id -> estado do job
JOBS_LOCK = threading.Lock()
MODEL_CACHE: dict[int, object] = {}  # experiment_id -> modelo carregado
MODEL_LOCK = threading.Lock()


class TrainIn(BaseModel):
    model_type: str = "rf"


def experiment_dict(row: sqlite3.Row) -> dict:
    exp = dict(row)
    for field in ("metrics", "classes", "feature_config"):
        exp[field] = json.loads(exp[field]) if exp[field] else None
    exp.pop("model_path", None)
    return exp


# ===== Extração com cache =====

def landmarks_for_example(example: dict, project_slug: str) -> dict | None:
    from vision import hands

    cache_dir = PROJECTS_DIR / project_slug / "landmarks"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{example['id']}.json"

    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    landmarks = hands.extract_from_file(PROJECTS_DIR / example["rel_path"])
    if landmarks is not None:
        cache_file.write_text(json.dumps(landmarks))
    return landmarks


# ===== Job de treinamento =====

def run_training(project_id: int, model_type: str) -> None:
    from vision.features import FEATURE_CONFIG, feature_vector
    from training import image_classifier

    job = JOBS[project_id]
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    try:
        project = db.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        examples = db.execute(
            """
            SELECT e.*, c.id AS cls_id, c.name AS cls_name
            FROM examples e JOIN classes c ON c.id = e.class_id
            WHERE c.project_id = ? AND e.kind = 'image'
            ORDER BY c.position, e.id
            """,
            (project_id,),
        ).fetchall()

        job.update(state="extracting", total=len(examples), done=0)
        X_rows, y_rows = [], []
        class_stats: dict[int, dict] = {}
        for ex in examples:
            stats = class_stats.setdefault(
                ex["cls_id"], {"id": ex["cls_id"], "name": ex["cls_name"],
                               "images": 0, "valid": 0})
            stats["images"] += 1
            landmarks = landmarks_for_example(dict(ex), project["slug"])
            vec = feature_vector(landmarks) if landmarks else None
            if vec is not None:
                stats["valid"] += 1
                X_rows.append(vec)
                y_rows.append(ex["cls_id"])
            job["done"] += 1

        if not X_rows:
            raise ValueError(
                "Nenhuma mão foi detectada nos exemplos de imagem. "
                "Verifique se as mãos aparecem com clareza nas fotos.")

        usable = {cid: s for cid, s in class_stats.items()
                  if s["valid"] >= image_classifier.MIN_VALID_PER_CLASS}
        mask = [cid in usable for cid in y_rows]
        X = np.array([x for x, m in zip(X_rows, mask) if m])
        y = np.array([c for c, m in zip(y_rows, mask) if m])

        job.update(state="training", message=None)
        class_names = {cid: s["name"] for cid, s in usable.items()}
        model, metrics = image_classifier.train(X, y, class_names, model_type)

        total_images = sum(s["images"] for s in class_stats.values())
        total_valid = sum(s["valid"] for s in class_stats.values())
        metrics["landmark_quality"] = round(total_valid / total_images, 4)

        classes_info = [
            {**s, "excluded": s["id"] not in usable}
            for s in class_stats.values()
        ]

        cur = db.execute(
            """
            INSERT INTO experiments (project_id, model_type, metrics, classes, feature_config)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, model_type, json.dumps(metrics),
             json.dumps(classes_info), json.dumps(FEATURE_CONFIG)),
        )
        exp_id = cur.lastrowid
        models_dir = PROJECTS_DIR / project["slug"] / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        model_path = models_dir / f"exp_{exp_id}.joblib"
        joblib.dump({"model": model, "class_names": class_names,
                     "feature_config": FEATURE_CONFIG}, model_path)
        db.execute("UPDATE experiments SET model_path = ? WHERE id = ?",
                   (str(model_path.relative_to(PROJECTS_DIR)), exp_id))
        db.commit()

        job.update(state="done", experiment_id=exp_id)
    except ValueError as err:
        job.update(state="error", message=str(err))
    except Exception as err:  # noqa: BLE001 — job precisa reportar qualquer falha
        job.update(state="error", message=f"Erro inesperado: {err}")
    finally:
        db.close()


@router.post("/projects/{project_id}/train", status_code=202)
def start_training(project_id: int, body: TrainIn,
                   db: sqlite3.Connection = Depends(get_db)):
    from training.image_classifier import MODEL_TYPES

    if body.model_type not in MODEL_TYPES:
        raise HTTPException(400, f"model_type deve ser um de: {MODEL_TYPES}")
    project_row(db, project_id)

    with JOBS_LOCK:
        job = JOBS.get(project_id)
        if job and job["state"] in ("extracting", "training"):
            raise HTTPException(409, "Já existe um treinamento em andamento.")
        JOBS[project_id] = {"state": "extracting", "done": 0, "total": 0,
                            "message": None, "experiment_id": None}

    thread = threading.Thread(target=run_training,
                              args=(project_id, body.model_type), daemon=True)
    thread.start()
    return {"started": True}


@router.get("/projects/{project_id}/train/status")
def training_status(project_id: int):
    return JOBS.get(project_id, {"state": "idle"})


@router.get("/projects/{project_id}/experiments")
def list_experiments(project_id: int, db: sqlite3.Connection = Depends(get_db)):
    project_row(db, project_id)
    rows = db.execute(
        "SELECT * FROM experiments WHERE project_id = ? ORDER BY id DESC",
        (project_id,),
    ).fetchall()
    return [experiment_dict(r) for r in rows]


def load_experiment_model(db: sqlite3.Connection, experiment_id: int):
    row = db.execute(
        "SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Experimento não encontrado")
    with MODEL_LOCK:
        bundle = MODEL_CACHE.get(experiment_id)
        if bundle is None:
            path = PROJECTS_DIR / row["model_path"]
            if not path.is_file():
                raise HTTPException(410, "Arquivo do modelo não existe mais")
            bundle = joblib.load(path)
            MODEL_CACHE[experiment_id] = bundle
    return row, bundle


@router.post("/experiments/{experiment_id}/predict")
async def predict(experiment_id: int, file: UploadFile,
                  db: sqlite3.Connection = Depends(get_db)):
    from vision import hands
    from vision.features import feature_vector

    _, bundle = load_experiment_model(db, experiment_id)
    data = await file.read()
    landmarks = hands.extract_from_bytes(data)
    if landmarks is None:
        raise HTTPException(400, "Arquivo de imagem inválido")

    vec = feature_vector(landmarks)
    hands_detected = int(bool(landmarks["left_hand"])) + int(bool(landmarks["right_hand"]))
    if vec is None:
        return {"hands_detected": 0, "predictions": [],
                "message": "Nenhuma mão detectada na imagem."}

    model = bundle["model"]
    class_names = bundle["class_names"]
    probs = model.predict_proba([vec])[0]
    ranking = [
        {"class": class_names[int(cls)], "prob": round(float(p), 4)}
        for cls, p in zip(model.classes_, probs)
    ]
    ranking.sort(key=lambda item: item["prob"], reverse=True)
    return {"hands_detected": hands_detected, "predictions": ranking}


@router.get("/experiments/{experiment_id}/export")
def export_experiment(experiment_id: int,
                      db: sqlite3.Connection = Depends(get_db)):
    row, _ = load_experiment_model(db, experiment_id)
    model_path = PROJECTS_DIR / row["model_path"]

    metadata = {
        "app": "SIGNLAB",
        "version": "1.0.0",
        "experiment_id": experiment_id,
        "model_type": row["model_type"],
        "model_file": "model.joblib",
        "metrics": json.loads(row["metrics"]),
        "classes": json.loads(row["classes"]),
        "feature_config": json.loads(row["feature_config"]),
        "created_at": row["created_at"],
        "usage": ("bundle = joblib.load('model.joblib'); "
                  "model = bundle['model']; class_names = bundle['class_names']"),
    }
    zip_path = model_path.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(model_path, "model.joblib")
        zf.writestr("metadata.json",
                    json.dumps(metadata, ensure_ascii=False, indent=2))
    return FileResponse(zip_path, media_type="application/zip",
                        filename=f"signlab_experimento_{experiment_id}.zip")

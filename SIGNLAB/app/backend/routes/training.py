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
MODEL_CACHE: dict[int, object] = {}  # experiment_id -> bundle carregado
MODEL_LOCK = threading.Lock()

# modalidade de cada tipo de modelo: imagem (estático) ou vídeo (temporal)
MODALITY = {"rf": "image", "mlp": "image", "bilstm": "video", "lstm": "video"}


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


def sequence_for_example(example: dict, project_slug: str, seq_len: int):
    """Sequência temporal do vídeo, com cache em sequences/<id>.npy + .json."""
    from vision import video as video_mod

    cache_dir = PROJECTS_DIR / project_slug / "sequences"
    cache_dir.mkdir(parents=True, exist_ok=True)
    npy_file = cache_dir / f"{example['id']}.npy"
    stats_file = cache_dir / f"{example['id']}.json"

    if npy_file.exists() and stats_file.exists():
        try:
            seq = np.load(npy_file)
            stats = json.loads(stats_file.read_text())
            if seq.shape[0] == seq_len:
                return seq, stats
        except (ValueError, json.JSONDecodeError, OSError):
            pass

    seq, stats = video_mod.extract_sequence_from_file(
        PROJECTS_DIR / example["rel_path"], seq_len)
    if seq is not None:
        np.save(npy_file, seq)
        stats_file.write_text(json.dumps(stats))
    return seq, stats


# ===== Job de treinamento =====

def _project_examples(db, project_id: int, kind: str):
    return db.execute(
        """
        SELECT e.*, c.id AS cls_id, c.name AS cls_name
        FROM examples e JOIN classes c ON c.id = e.class_id
        WHERE c.project_id = ? AND e.kind = ?
        ORDER BY c.position, e.id
        """,
        (project_id, kind),
    ).fetchall()


def _save_experiment(db, project, model_type: str, metrics: dict,
                     classes_info: list, feature_config: dict,
                     save_model) -> int:
    """Insere o experimento, salva o modelo via callback e grava o caminho."""
    cur = db.execute(
        """
        INSERT INTO experiments (project_id, model_type, metrics, classes, feature_config)
        VALUES (?, ?, ?, ?, ?)
        """,
        (project["id"], model_type, json.dumps(metrics),
         json.dumps(classes_info), json.dumps(feature_config)),
    )
    exp_id = cur.lastrowid
    models_dir = PROJECTS_DIR / project["slug"] / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    model_path = save_model(models_dir, exp_id)
    db.execute("UPDATE experiments SET model_path = ? WHERE id = ?",
               (str(model_path.relative_to(PROJECTS_DIR)), exp_id))
    db.commit()
    return exp_id


def _train_image(db, job, project, project_id: int, model_type: str) -> int:
    from vision.features import FEATURE_CONFIG, feature_vector
    from training import image_classifier

    examples = _project_examples(db, project_id, "image")
    job.update(state="extracting", total=len(examples), done=0)

    X_rows, y_rows = [], []
    class_stats: dict[int, dict] = {}
    for ex in examples:
        stats = class_stats.setdefault(
            ex["cls_id"], {"id": ex["cls_id"], "name": ex["cls_name"],
                           "examples": 0, "valid": 0})
        stats["examples"] += 1
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

    total = sum(s["examples"] for s in class_stats.values())
    valid = sum(s["valid"] for s in class_stats.values())
    metrics["landmark_quality"] = round(valid / total, 4)
    classes_info = [{**s, "excluded": s["id"] not in usable}
                    for s in class_stats.values()]

    def save_model(models_dir, exp_id):
        path = models_dir / f"exp_{exp_id}.joblib"
        joblib.dump({"model": model, "class_names": class_names,
                     "feature_config": FEATURE_CONFIG}, path)
        return path

    return _save_experiment(db, project, model_type, metrics,
                            classes_info, FEATURE_CONFIG, save_model)


def _train_video(db, job, project, project_id: int, model_type: str) -> int:
    from vision.features import FEATURE_CONFIG
    from vision.video import DEFAULT_SEQUENCE_LENGTH
    from training import sequence_classifier

    seq_len = DEFAULT_SEQUENCE_LENGTH
    examples = _project_examples(db, project_id, "video")
    job.update(state="extracting", total=len(examples), done=0)

    X_rows, y_rows, qualities = [], [], []
    class_stats: dict[int, dict] = {}
    for ex in examples:
        stats = class_stats.setdefault(
            ex["cls_id"], {"id": ex["cls_id"], "name": ex["cls_name"],
                           "examples": 0, "valid": 0})
        stats["examples"] += 1
        seq, seq_stats = sequence_for_example(dict(ex), project["slug"], seq_len)
        # sequência entra se um mínimo dos frames tem mão detectada
        if seq is not None and seq_stats["quality"] >= 0.25:
            stats["valid"] += 1
            X_rows.append(seq)
            y_rows.append(ex["cls_id"])
            qualities.append(seq_stats["quality"])
        job["done"] += 1

    if not X_rows:
        raise ValueError(
            "Nenhum vídeo com mãos detectadas. Verifique se as mãos "
            "aparecem com clareza e boa iluminação nos vídeos.")

    usable = {cid: s for cid, s in class_stats.items()
              if s["valid"] >= sequence_classifier.MIN_VALID_PER_CLASS}
    mask = [cid in usable for cid in y_rows]
    X = np.stack([x for x, m in zip(X_rows, mask) if m])
    y = np.array([c for c, m in zip(y_rows, mask) if m])

    job.update(state="training", message=None)
    class_names = {cid: s["name"] for cid, s in usable.items()}
    model, labels, metrics = sequence_classifier.train(
        X, y, class_names, model_type)

    metrics["landmark_quality"] = round(
        float(np.mean([q for q, m in zip(qualities, mask) if m])), 4)
    classes_info = [{**s, "excluded": s["id"] not in usable}
                    for s in class_stats.values()]
    feature_config = {**FEATURE_CONFIG, "temporal": True,
                      "sequence_length": seq_len}

    def save_model(models_dir, exp_id):
        path = models_dir / f"exp_{exp_id}.keras"
        model.save(path)
        meta = {"labels": labels,
                "class_names": {str(k): v for k, v in class_names.items()},
                "sequence_length": seq_len,
                "feature_config": feature_config}
        (models_dir / f"exp_{exp_id}.meta.json").write_text(
            json.dumps(meta, ensure_ascii=False))
        return path

    return _save_experiment(db, project, model_type, metrics,
                            classes_info, feature_config, save_model)


def run_training(project_id: int, model_type: str) -> None:
    job = JOBS[project_id]
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    try:
        project = dict(db.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())
        if MODALITY[model_type] == "video":
            exp_id = _train_video(db, job, project, project_id, model_type)
        else:
            exp_id = _train_image(db, job, project, project_id, model_type)
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
    if body.model_type not in MODALITY:
        raise HTTPException(400,
                            f"model_type deve ser um de: {tuple(MODALITY)}")
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
            if MODALITY[row["model_type"]] == "video":
                import keras
                meta = json.loads(
                    path.with_name(f"{path.stem}.meta.json").read_text())
                bundle = {
                    "temporal": True,
                    "model": keras.models.load_model(path),
                    "labels": meta["labels"],
                    "class_names": {int(k): v
                                    for k, v in meta["class_names"].items()},
                    "seq_len": meta["sequence_length"],
                }
            else:
                bundle = joblib.load(path)
            MODEL_CACHE[experiment_id] = bundle
    return row, bundle


@router.post("/experiments/{experiment_id}/predict")
async def predict(experiment_id: int, file: UploadFile,
                  db: sqlite3.Connection = Depends(get_db)):
    _, bundle = load_experiment_model(db, experiment_id)
    data = await file.read()

    if bundle.get("temporal"):
        from vision.video import extract_sequence_from_bytes

        seq, stats = extract_sequence_from_bytes(
            data, file.filename or "video.mp4", bundle["seq_len"])
        if seq is None:
            raise HTTPException(400, "Não foi possível ler o vídeo enviado")
        if stats["frames_with_hands"] == 0:
            return {"predictions": [], "stats": stats,
                    "message": "Nenhuma mão detectada no vídeo."}
        probs = bundle["model"].predict(seq[None, ...], verbose=0)[0]
        ranking = [
            {"class": bundle["class_names"][label], "prob": round(float(p), 4)}
            for label, p in zip(bundle["labels"], probs)
        ]
        ranking.sort(key=lambda item: item["prob"], reverse=True)
        return {"predictions": ranking, "stats": stats}

    from vision import hands
    from vision.features import feature_vector

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

    temporal = MODALITY[row["model_type"]] == "video"
    model_file = "model.keras" if temporal else "model.joblib"
    usage = (
        "import keras, json; model = keras.models.load_model('model.keras'); "
        "meta = json.load(open('metadata.json')); labels = meta['labels'] "
        "# ordem das classes na saída softmax"
    ) if temporal else (
        "bundle = joblib.load('model.joblib'); "
        "model = bundle['model']; class_names = bundle['class_names']"
    )
    metadata = {
        "app": "SIGNLAB",
        "version": "1.0.0",
        "experiment_id": experiment_id,
        "model_type": row["model_type"],
        "model_file": model_file,
        "metrics": json.loads(row["metrics"]),
        "classes": json.loads(row["classes"]),
        "feature_config": json.loads(row["feature_config"]),
        "created_at": row["created_at"],
        "usage": usage,
    }
    if temporal:
        meta_path = model_path.with_name(f"{model_path.stem}.meta.json")
        meta = json.loads(meta_path.read_text())
        metadata["labels"] = [meta["class_names"][str(l)]
                              for l in meta["labels"]]
    zip_path = model_path.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(model_path, model_file)
        zf.writestr("metadata.json",
                    json.dumps(metadata, ensure_ascii=False, indent=2))
    return FileResponse(zip_path, media_type="application/zip",
                        filename=f"signlab_experimento_{experiment_id}.zip")

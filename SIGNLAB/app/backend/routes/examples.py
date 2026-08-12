import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from ..database import get_db
from .. import storage
from .classes import class_row
from .projects import touch_project

router = APIRouter(prefix="/api", tags=["examples"])


@router.get("/classes/{class_id}/examples")
def list_examples(class_id: int, limit: int = 0, db: sqlite3.Connection = Depends(get_db)):
    class_row(db, class_id)
    if limit <= 0:
        return []  # ponytail: large projects (1000+ classes) shouldn't preload all examples
    query = "SELECT * FROM examples WHERE class_id = ? ORDER BY id DESC"
    if limit > 0:
        query += f" LIMIT {limit}"
    rows = db.execute(query, (class_id,)).fetchall()
    return [dict(r) for r in rows]


@router.post("/classes/{class_id}/examples", status_code=201)
async def upload_examples(class_id: int,
                          files: list[UploadFile],
                          source: str = Form("upload"),
                          db: sqlite3.Connection = Depends(get_db)):
    if source not in ("upload", "webcam"):
        raise HTTPException(400, "source deve ser 'upload' ou 'webcam'")
    row = class_row(db, class_id)

    saved, rejected = [], []
    for file in files:
        kind = storage.kind_for(file.filename or "")
        if not kind:
            rejected.append(file.filename)
            continue
        data = await file.read()
        name, rel_path = storage.save_example(
            row["project_slug"], row["slug"], kind, file.filename, data
        )
        cur = db.execute(
            """
            INSERT INTO examples (class_id, kind, source, filename, rel_path, size_bytes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (class_id, kind, source, name, rel_path, len(data)),
        )
        example = db.execute(
            "SELECT * FROM examples WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        saved.append(dict(example))

    if saved:
        touch_project(db, row["project_id"])
    return {"saved": saved, "rejected": rejected}


@router.delete("/examples/{example_id}", status_code=204)
def delete_example(example_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute(
        "SELECT * FROM examples WHERE id = ?", (example_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Exemplo não encontrado")
    cls = class_row(db, row["class_id"])
    db.execute("DELETE FROM examples WHERE id = ?", (example_id,))
    touch_project(db, cls["project_id"])
    storage.delete_file(row["rel_path"])

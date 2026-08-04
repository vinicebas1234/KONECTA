import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import get_db
from .. import storage
from .projects import project_row, touch_project, unique_slug

router = APIRouter(prefix="/api", tags=["classes"])


class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


def class_row(db: sqlite3.Connection, class_id: int) -> sqlite3.Row:
    row = db.execute(
        """
        SELECT c.*, p.slug AS project_slug
        FROM classes c JOIN projects p ON p.id = c.project_id
        WHERE c.id = ?
        """,
        (class_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Classe não encontrada")
    return row


@router.post("/projects/{project_id}/classes", status_code=201)
def create_class(project_id: int, body: ClassIn,
                 db: sqlite3.Connection = Depends(get_db)):
    project_row(db, project_id)
    slug = unique_slug(db, "classes", body.name,
                       "AND project_id = ?", (project_id,))
    position = db.execute(
        "SELECT COALESCE(MAX(position), 0) + 1 FROM classes WHERE project_id = ?",
        (project_id,),
    ).fetchone()[0]
    cur = db.execute(
        "INSERT INTO classes (project_id, name, slug, position) VALUES (?, ?, ?, ?)",
        (project_id, body.name.strip(), slug, position),
    )
    touch_project(db, project_id)
    return dict(class_row(db, cur.lastrowid))


@router.patch("/classes/{class_id}")
def rename_class(class_id: int, body: ClassIn,
                 db: sqlite3.Connection = Depends(get_db)):
    row = class_row(db, class_id)
    db.execute("UPDATE classes SET name = ? WHERE id = ?",
               (body.name.strip(), class_id))
    touch_project(db, row["project_id"])
    return dict(class_row(db, class_id))


@router.delete("/classes/{class_id}", status_code=204)
def delete_class(class_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = class_row(db, class_id)
    db.execute("DELETE FROM classes WHERE id = ?", (class_id,))
    touch_project(db, row["project_id"])
    storage.delete_class_files(row["project_slug"], row["slug"])

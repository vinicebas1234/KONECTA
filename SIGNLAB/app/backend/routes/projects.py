import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import get_db
from .. import storage

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


def unique_slug(db: sqlite3.Connection, table: str, name: str,
                extra_where: str = "", params: tuple = ()) -> str:
    base = storage.slugify(name)
    slug = base
    n = 2
    while db.execute(
        f"SELECT 1 FROM {table} WHERE slug = ? {extra_where}", (slug, *params)
    ).fetchone():
        slug = f"{base}-{n}"
        n += 1
    return slug


def touch_project(db: sqlite3.Connection, project_id: int) -> None:
    db.execute(
        "UPDATE projects SET updated_at = datetime('now') WHERE id = ?",
        (project_id,),
    )


def project_row(db: sqlite3.Connection, project_id: int) -> sqlite3.Row:
    row = db.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Projeto não encontrado")
    return row


def class_summaries(db: sqlite3.Connection, project_id: int) -> list[dict]:
    rows = db.execute(
        """
        SELECT c.id, c.name, c.slug, c.position, c.created_at,
               COALESCE(SUM(CASE WHEN e.kind = 'image' AND e.source = 'upload' THEN 1 END), 0) AS images,
               COALESCE(SUM(CASE WHEN e.kind = 'video' AND e.source = 'upload' THEN 1 END), 0) AS videos,
               COALESCE(SUM(CASE WHEN e.source = 'webcam' THEN 1 END), 0) AS captures,
               COUNT(e.id) AS total
        FROM classes c
        LEFT JOIN examples e ON e.class_id = c.id
        WHERE c.project_id = ?
        GROUP BY c.id
        ORDER BY c.position, c.id
        """,
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("")
def list_projects(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        """
        SELECT p.*,
               (SELECT COUNT(*) FROM classes c WHERE c.project_id = p.id) AS class_count,
               (SELECT COUNT(*) FROM examples e
                JOIN classes c ON c.id = e.class_id
                WHERE c.project_id = p.id) AS example_count
        FROM projects p
        ORDER BY p.updated_at DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


@router.post("", status_code=201)
def create_project(body: ProjectIn, db: sqlite3.Connection = Depends(get_db)):
    slug = unique_slug(db, "projects", body.name)
    cur = db.execute(
        "INSERT INTO projects (name, slug) VALUES (?, ?)", (body.name.strip(), slug)
    )
    storage.create_project_dirs(slug)
    return dict(project_row(db, cur.lastrowid))


@router.get("/{project_id}")
def get_project(project_id: int, db: sqlite3.Connection = Depends(get_db)):
    project = dict(project_row(db, project_id))
    project["classes"] = class_summaries(db, project_id)
    return project


@router.patch("/{project_id}")
def rename_project(project_id: int, body: ProjectIn,
                   db: sqlite3.Connection = Depends(get_db)):
    project_row(db, project_id)
    db.execute(
        "UPDATE projects SET name = ?, updated_at = datetime('now') WHERE id = ?",
        (body.name.strip(), project_id),
    )
    return dict(project_row(db, project_id))


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = project_row(db, project_id)
    db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    storage.delete_project_files(row["slug"])

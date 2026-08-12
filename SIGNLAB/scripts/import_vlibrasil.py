#!/usr/bin/env python3
"""
Script para importar o dataset V-LIBRASIL completo para o SIGNLAB.
Uso: python import_vlibrasil.py
"""
import os
import sqlite3
import sys
from pathlib import Path
from app.backend import storage
from app.backend.database import init_db

VLIBRASIL_PATH = Path("C:/KONECTA/Datasets/videos UFPE (V-LIBRASIL)/data")
DB_PATH = Path(__file__).parent.parent / "data" / "signlab.db"

def import_vlibrasil():
    """Importa o dataset V-LIBRASIL para um novo projeto no SIGNLAB."""

    if not VLIBRASIL_PATH.exists():
        print(f"[ERRO] Caminho nao encontrado: {VLIBRASIL_PATH}")
        print("Verifique o caminho do dataset V-LIBRASIL")
        return

    # Inicializar banco se necessário
    init_db()

    # Conectar ao banco
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row

    # Verificar se projeto já existe
    existing = db.execute(
        "SELECT id FROM projects WHERE slug = ?",
        ("vlibrasil-completo",)
    ).fetchone()

    if existing:
        print("[OK] Projeto V-LIBRASIL Completo ja existe!")
        project_id = existing[0]
        print(f"   Continuando importacao para projeto ID {project_id}...")
    else:
        # Criar novo projeto
        print("[OK] Criando projeto V-LIBRASIL completo...")
        cur = db.execute(
            "INSERT INTO projects (name, slug) VALUES (?, ?)",
            ("V-LIBRASIL Completo", "vlibrasil-completo")
        )
        project_id = cur.lastrowid
        db.commit()
        print(f"   Projeto criado com ID {project_id}")

    project_row = db.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    project_slug = dict(project_row)["slug"]

    # Listar sinais
    sinais = sorted([d for d in VLIBRASIL_PATH.iterdir() if d.is_dir()])
    print(f"[INFO] Encontrados {len(sinais)} sinais")

    imported = 0
    for sinal_dir in sinais:
        sinal_name = sinal_dir.name

        # Verificar se classe já existe
        existing_class = db.execute(
            "SELECT id FROM classes WHERE project_id = ? AND slug = ?",
            (project_id, sinal_name.lower())
        ).fetchone()

        if existing_class:
            class_id = existing_class[0]
        else:
            # Criar classe
            cur = db.execute(
                "INSERT INTO classes (project_id, name, slug) VALUES (?, ?, ?)",
                (project_id, sinal_name, sinal_name.lower())
            )
            class_id = cur.lastrowid
            db.commit()

        # Listar arquivos (imagens e vídeos)
        videos = sorted(sinal_dir.glob("*.mp4")) + sorted(sinal_dir.glob("*.webm"))

        print(f"  [DIR] {sinal_name}: {len(videos)} videos")

        for video_file in videos:
            try:
                # Verificar se exemplo já existe
                existing_example = db.execute(
                    "SELECT id FROM examples WHERE class_id = ? AND filename = ?",
                    (class_id, video_file.name)
                ).fetchone()

                if existing_example:
                    continue  # Já foi importado, pula

                # Ler arquivo
                data = video_file.read_bytes()

                # Salvar no storage
                kind = "video"
                name, rel_path = storage.save_example(
                    project_slug, sinal_name.lower(), kind,
                    video_file.name, data
                )

                # Inserir no banco
                db.execute(
                    """INSERT INTO examples
                       (class_id, kind, source, filename, rel_path, size_bytes)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (class_id, kind, "upload", name, rel_path, len(data))
                )
                db.commit()
                imported += 1

                if imported % 50 == 0:
                    print(f"    [OK] {imported} videos importados...")

            except Exception as e:
                print(f"    [ERRO] Erro ao importar {video_file.name}: {e}")

    print(f"\n[OK] Importacao concluida!")
    print(f"   Projeto: V-LIBRASIL Completo")
    print(f"   Sinais: {len(sinais)}")
    print(f"   Videos: {imported}")
    print(f"   Acesse em: http://localhost:8100/#/p/{project_id}")

    # Fechar conexão
    try:
        db.commit()
        db.close()
    except:
        pass

if __name__ == "__main__":
    import_vlibrasil()

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
from app.backend.database import get_db

VLIBRASIL_PATH = Path("C:/KONECTA/Datasets/videos UFPE (V-LIBRASIL)/data")

def import_vlibrasil():
    """Importa o dataset V-LIBRASIL para um novo projeto no SIGNLAB."""

    if not VLIBRASIL_PATH.exists():
        print(f"❌ Caminho não encontrado: {VLIBRASIL_PATH}")
        print("Verif ique o caminho do dataset V-LIBRASIL")
        return

    # Conectar ao banco
    db = next(get_db())

    # Criar novo projeto
    print("📋 Criando projeto V-LIBRASIL completo...")
    cur = db.execute(
        "INSERT INTO projects (name, slug) VALUES (?, ?)",
        ("V-LIBRASIL Completo", "vlibrasil-completo")
    )
    project_id = cur.lastrowid
    db.commit()

    project_row = db.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    project_slug = dict(project_row)["slug"]

    # Listar sinais
    sinais = sorted([d for d in VLIBRASIL_PATH.iterdir() if d.is_dir()])
    print(f"🔤 Encontrados {len(sinais)} sinais")

    imported = 0
    for sinal_dir in sinais:
        sinal_name = sinal_dir.name

        # Criar classe
        cur = db.execute(
            "INSERT INTO classes (project_id, name, slug) VALUES (?, ?, ?)",
            (project_id, sinal_name, sinal_name.lower())
        )
        class_id = cur.lastrowid
        db.commit()

        # Listar arquivos (imagens e vídeos)
        videos = sorted(sinal_dir.glob("*.mp4")) + sorted(sinal_dir.glob("*.webm"))

        print(f"  📁 {sinal_name}: {len(videos)} vídeos")

        for video_file in videos:
            try:
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
                    (class_id, kind, "import", name, rel_path, len(data))
                )
                db.commit()
                imported += 1

                if imported % 50 == 0:
                    print(f"    ✓ {imported} vídeos importados...")

            except Exception as e:
                print(f"    ❌ Erro ao importar {video_file.name}: {e}")

    print(f"\n✅ Importação concluída!")
    print(f"   Projeto: V-LIBRASIL Completo")
    print(f"   Sinais: {len(sinais)}")
    print(f"   Vídeos: {imported}")
    print(f"   Acesse em: http://localhost:8100/#/p/{project_id}")

    db.close()

if __name__ == "__main__":
    import_vlibrasil()

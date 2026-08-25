#!/usr/bin/env python3
"""
Script para importar o dataset V-LIBRASIL completo para o SIGNLAB.
Uso: python import_vlibrasil.py
"""
import os
import re
import sqlite3
import sys
from pathlib import Path

# Este script vive em scripts/, mas importa o pacote app/ da raiz.
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# O console do Windows e' cp1252 e alguns nomes do V-LIBRASIL tem caracteres
# fora dele. Sem isto, um print derruba a importacao inteira no meio -- ja
# aconteceu depois de 2,7 GB copiados.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.backend import storage
from app.backend.database import init_db
from app.backend.routes.projects import unique_slug

# Sobrescrevivel para testar o fluxo num punhado de classes antes de
# comprometer os 11 GB do dataset inteiro.
VLIBRASIL_PATH = Path(os.environ.get(
    "VLIBRASIL_PATH", "C:/KONECTA/Datasets/videos UFPE (V-LIBRASIL)/data"))
DB_PATH = RAIZ / "data" / "signlab.db"

# O V-LIBRASIL tem 3 sinalizantes e o nome do arquivo diz qual:
# "Abacaxi_Articulador1.mp4". Sem gravar isso, todo exemplo entra como
# 'unknown' -- e em training.py o 'unknown' entra SEMPRE no treino, entao um
# experimento cross-signer treinaria com tudo e testaria com nada, reportando
# uma acuracia alta e falsa.
_SINALIZANTE = re.compile(r"articulador\s*(\d+)", re.IGNORECASE)


def limpar_nome(nome: str) -> str:
    """Traduz caracteres de area privada (U+F000-U+F0FF) para ASCII.

    Tres classes do V-LIBRASIL vem com resquicio de fonte simbolica: o nome
    guarda U+F022 onde deveria haver aspas, U+F03F onde havia "?" e U+F05C
    onde havia "\\". Nesse bloco o byte baixo e' o proprio codigo ASCII, entao
    a traducao e' direta -- e sem ela o nome fica ilegivel na interface.
    """
    return "".join(
        chr(ord(c) - 0xF000) if 0xF000 <= ord(c) <= 0xF0FF else c
        for c in nome
    )


def sinalizante_de(nome: str) -> str:
    """Extrai o sinalizante do nome do arquivo, em forma canonica.

    Aceita tanto o nome original ("Abacaxi_Articulador1.mp4") quanto o ja
    slugificado pelo storage ("a1b2c3d4_abacaxi-articulador1.mp4"), porque o
    reparo abaixo le o nome como ficou gravado.
    """
    achou = _SINALIZANTE.search(nome)
    return f"Articulador{achou.group(1)}" if achou else "unknown"

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

    # Versoes anteriores deste script nao gravavam signer_name. Corrige o que
    # ja esta no banco em vez de exigir reimportar 11 GB.
    pendentes = db.execute(
        """SELECT e.id, e.filename FROM examples e
           JOIN classes c ON c.id = e.class_id
           WHERE c.project_id = ? AND e.signer_name = 'unknown'""",
        (project_id,),
    ).fetchall()
    reparados = 0
    for linha in pendentes:
        quem = sinalizante_de(linha["filename"])
        if quem != "unknown":
            db.execute("UPDATE examples SET signer_name = ? WHERE id = ?",
                       (quem, linha["id"]))
            reparados += 1
    if reparados:
        db.commit()
        print(f"[OK] signer_name corrigido em {reparados} exemplos ja importados")

    # Listar sinais
    sinais = sorted([d for d in VLIBRASIL_PATH.iterdir() if d.is_dir()])
    print(f"[INFO] Encontrados {len(sinais)} sinais")

    imported = 0
    for sinal_dir in sinais:
        sinal_name = limpar_nome(sinal_dir.name)

        # A busca e' pelo NOME, nao pelo slug: "Avo" com acento agudo e com
        # circunflexo slugificam igual, e casar por slug fundia as duas numa
        # classe so', descartando os videos da segunda como se fossem
        # duplicata. Sao sinais diferentes.
        existing_class = db.execute(
            "SELECT id, slug FROM classes WHERE project_id = ? AND name = ?",
            (project_id, sinal_name)
        ).fetchone()

        if existing_class:
            class_id, class_slug = existing_class[0], existing_class[1]
        else:
            # O slug vira nome de pasta em storage.example_dir. Usar
            # name.lower() deixava passar o que o Windows recusa:
            # "Frente\ Frente" criava pasta aninhada e "O que?" e' invalido.
            # unique_slug slugifica e desempata colisoes com sufixo -2.
            class_slug = unique_slug(db, "classes", sinal_name,
                                     "AND project_id = ?", (project_id,))
            cur = db.execute(
                "INSERT INTO classes (project_id, name, slug) VALUES (?, ?, ?)",
                (project_id, sinal_name, class_slug)
            )
            class_id = cur.lastrowid
            db.commit()

        # Listar arquivos (imagens e vídeos)
        videos = sorted(sinal_dir.glob("*.mp4")) + sorted(sinal_dir.glob("*.webm"))

        print(f"  [DIR] {sinal_name}: {len(videos)} videos")

        for video_file in videos:
            try:
                # storage.save_example grava como "<uuid8>_<stem-slug><ext>",
                # com uuid novo a cada chamada -- entao comparar com o nome de
                # origem NUNCA casava e cada reexecucao duplicava tudo. Ja
                # rendeu 5148 exemplos para 4086 videos. O sufixo e' estavel.
                marca = f"%_{storage.slugify(video_file.stem)}{video_file.suffix.lower()}"
                existing_example = db.execute(
                    "SELECT id FROM examples WHERE class_id = ? AND filename LIKE ?",
                    (class_id, marca)
                ).fetchone()

                if existing_example:
                    continue  # Já foi importado, pula

                # Ler arquivo
                data = video_file.read_bytes()

                # Salvar no storage
                kind = "video"
                name, rel_path = storage.save_example(
                    project_slug, class_slug, kind,
                    video_file.name, data
                )

                # Inserir no banco
                db.execute(
                    """INSERT INTO examples
                       (class_id, kind, source, filename, rel_path, size_bytes,
                        signer_name)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (class_id, kind, "upload", name, rel_path, len(data),
                     sinalizante_de(video_file.name))
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

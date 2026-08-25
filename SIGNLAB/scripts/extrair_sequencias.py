#!/usr/bin/env python3
"""Extrai as sequencias de landmarks em paralelo, no mesmo cache que o treino usa.

Motivo: o treino extrai serialmente, um video por vez. Medido nesta maquina,
cada video leva ~4s -- com 4092 videos sao 4,6 h com a tela do SIGNLAB parada
em "treinando". Aqui o trabalho e' identico, so' dividido entre processos, e
como grava em projects/<slug>/sequences/<id>.npy (o cache que training.py le'),
o treino seguinte so' carrega os .npy e comeca na hora.

Roda quantas vezes quiser: o que ja esta em cache e' pulado.

Uso:
    python scripts/extrair_sequencias.py vlibrasil-completo
    python scripts/extrair_sequencias.py vlibrasil-completo --processos 4
"""
import argparse
import sqlite3
import sys
import time
from multiprocessing import Pool, cpu_count
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

DB_PATH = RAIZ / "data" / "signlab.db"
SEQ_LEN = 30


def _extrair(tarefa):
    """Roda no processo filho. Devolve (id, qualidade) ou (id, None) se falhou."""
    from app.backend.routes.training import sequence_for_example

    exemplo_id, rel_path, slug = tarefa
    try:
        seq, stats = sequence_for_example(
            {"id": exemplo_id, "rel_path": rel_path}, slug, SEQ_LEN)
    except Exception as erro:                      # video corrompido, codec, etc
        return exemplo_id, None, str(erro)[:60]
    if seq is None:
        return exemplo_id, None, "sem sequencia"
    return exemplo_id, stats["frames_with_hands"] / stats["frames_sampled"], None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", help="slug do projeto (ex: vlibrasil-completo)")
    ap.add_argument("--processos", type=int, default=max(1, cpu_count() - 2),
                    help="padrao: nucleos - 2, para a maquina seguir usavel")
    args = ap.parse_args()

    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    projeto = db.execute("SELECT id, slug FROM projects WHERE slug = ?",
                         (args.slug,)).fetchone()
    if projeto is None:
        existentes = [r["slug"] for r in db.execute("SELECT slug FROM projects")]
        sys.exit(f"[ERRO] projeto '{args.slug}' nao existe. Ha: {existentes}")

    exemplos = db.execute(
        """SELECT e.id, e.rel_path FROM examples e
           JOIN classes c ON c.id = e.class_id
           WHERE c.project_id = ? AND e.kind = 'video'
           ORDER BY e.id""",
        (projeto["id"],),
    ).fetchall()
    db.close()

    cache = RAIZ / "projects" / projeto["slug"] / "sequences"
    pendentes = [
        (e["id"], e["rel_path"], projeto["slug"]) for e in exemplos
        if not ((cache / f"{e['id']}.npy").exists()
                and (cache / f"{e['id']}.json").exists())
    ]

    print(f"[INFO] {len(exemplos)} videos no projeto, "
          f"{len(exemplos) - len(pendentes)} ja em cache, "
          f"{len(pendentes)} a extrair")
    if not pendentes:
        print("[OK] nada a fazer")
        return

    print(f"[INFO] {args.processos} processos "
          f"(cada um carrega o MediaPipe uma vez, ~20s)\n")

    inicio = time.perf_counter()
    qualidades, falhas = [], []
    with Pool(args.processos) as pool:
        for i, (eid, q, erro) in enumerate(
                pool.imap_unordered(_extrair, pendentes, chunksize=4), 1):
            if erro:
                falhas.append((eid, erro))
            else:
                qualidades.append(q)
            if i % 50 == 0 or i == len(pendentes):
                decorrido = time.perf_counter() - inicio
                resta = decorrido / i * (len(pendentes) - i)
                print(f"  {i}/{len(pendentes)}  "
                      f"{decorrido/60:.1f} min decorridos, "
                      f"~{resta/60:.0f} min restantes")

    print(f"\n[OK] {len(qualidades)} extraidos em "
          f"{(time.perf_counter() - inicio)/60:.1f} min")

    if qualidades:
        # A fracao de frames com mao detectada e' o que separa um exemplo util
        # de ruido. Abaixo de 50% o video quase nao contribui para o treino.
        media = sum(qualidades) / len(qualidades)
        ruins = sum(1 for q in qualidades if q < 0.5)
        print(f"     qualidade media das maos: {media:.0%}")
        print(f"     abaixo de 50%: {ruins} ({ruins/len(qualidades):.1%})")
    if falhas:
        print(f"\n[AVISO] {len(falhas)} falharam:")
        for eid, erro in falhas[:10]:
            print(f"     exemplo {eid}: {erro}")


if __name__ == "__main__":
    main()

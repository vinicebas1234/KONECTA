"""API do app de gravação (a PWA em /app/, instalada no celular).

Tudo aqui fica preso ao projeto configurado em ``data/app.json``: com o link
do celular se grava e se cria sinal nesse projeto, e só (ver acesso.py).

Só landmarks: o vídeo chega, o mesmo pipeline do treino
(``vision.video.extract_sequence_from_file``) extrai a sequência e o vídeo é
apagado. O ``.npy`` em ``projects/<slug>/sequences/<id>.npy`` deixa de ser
cache e vira o único registro da gravação — o ``rel_path`` do exemplo aponta
para ele, então excluir o exemplo no admin apaga os landmarks junto.
"""
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from ..database import DB_PATH, ROOT, get_db
from ..storage import PROJECTS_DIR
from .classes import ClassIn, create_class
from .projects import touch_project

router = APIRouter(prefix="/app-api", tags=["app"])

CONFIG = DB_PATH.parent / "app.json"
ESTADO = DB_PATH.parent / "app_publicacao.json"
PADRAO = {
    "projeto_id": None,
    "meta_por_sinal": 10,
    "modelo": "bilstm",
    # Abaixo disto o modelo novo não substitui o do KONECTA (publicador.py).
    "acuracia_minima": 0.6,
    # Treina quando as gravações param de chegar por este tempo, para não
    # treinar a cada envio no meio de uma sessão de 10 repetições.
    "espera_s": 180,
    "publicar_em": str(ROOT.parent / "KONECTA_V3" / "models"),
}

MAX_BYTES = 25 * 1024 * 1024
# O mesmo corte de training._train_video: abaixo disso o treino descarta a
# sequência. Recusar aqui dá o aviso na hora, com ela ainda gravando.
QUALIDADE_MINIMA = 0.25
# A webcam do KONECTA captura 640x480. As coordenadas do MediaPipe são
# normalizadas por eixo e features.normalize_hand não corrige proporção, então
# um vídeo em outra proporção gera geometria que o KONECTA nunca vê.
PROPORCAO = 4 / 3


def ler_config() -> dict:
    dados = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    return {**PADRAO, **dados}


def salvar_config(**mudancas) -> dict:
    dados = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    dados.update(mudancas)
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
    return {**PADRAO, **dados}


def ler_estado() -> dict:
    if ESTADO.exists():
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    return {"publicado_ate": 0, "estado": "ocioso"}


def salvar_estado(**mudancas) -> dict:
    dados = {**ler_estado(), **mudancas}
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
    return dados


def _projeto(db: sqlite3.Connection) -> tuple[sqlite3.Row, dict]:
    cfg = ler_config()
    if not cfg["projeto_id"]:
        raise HTTPException(503, "O app ainda não foi configurado no computador.")
    projeto = db.execute("SELECT * FROM projects WHERE id = ?",
                         (cfg["projeto_id"],)).fetchone()
    if projeto is None:
        raise HTTPException(503, "O projeto configurado para o app não existe mais.")
    return projeto, cfg


def _contagem(db, class_id: int, sinalizante: str) -> tuple[int, int]:
    total, meus = db.execute(
        """SELECT COUNT(*), COALESCE(SUM(signer_name = ?), 0) FROM examples
           WHERE class_id = ? AND kind = 'video'""",
        (sinalizante, class_id)).fetchone()
    return meus, total


@router.get("/estado")
def estado(sinalizante: str = "", db: sqlite3.Connection = Depends(get_db)):
    projeto, cfg = _projeto(db)
    sinais = db.execute(
        """SELECT c.id, c.name, COUNT(e.id) AS total,
                  COALESCE(SUM(e.signer_name = ?), 0) AS meus
           FROM classes c
           LEFT JOIN examples e ON e.class_id = c.id AND e.kind = 'video'
           WHERE c.project_id = ?
           GROUP BY c.id ORDER BY c.position, c.id""",
        (sinalizante, projeto["id"])).fetchall()
    return {
        "projeto": projeto["name"],
        "meta": cfg["meta_por_sinal"],
        "sinais": [{"id": s["id"], "nome": s["name"], "total": s["total"],
                    "meus": s["meus"]} for s in sinais],
        "publicacao": ler_estado(),
    }


class SinalIn(BaseModel):
    nome: str = Field(min_length=1, max_length=60)


@router.post("/sinais", status_code=201)
def criar_sinal(body: SinalIn, response: Response,
                db: sqlite3.Connection = Depends(get_db)):
    projeto, _ = _projeto(db)
    nome = " ".join(body.nome.split())
    if not nome:
        raise HTTPException(400, "Dê um nome ao sinal.")
    # casefold em Python: o lower() do SQLite só dobra ASCII, e "MÃE" passaria
    # como sinal novo ao lado de "Mãe".
    for linha in db.execute("SELECT id, name FROM classes WHERE project_id = ?",
                            (projeto["id"],)):
        if linha["name"].casefold() == nome.casefold():
            response.status_code = 200
            return {"id": linha["id"], "nome": linha["name"], "novo": False}
    criada = create_class(projeto["id"], ClassIn(name=nome), db)
    return {"id": criada["id"], "nome": criada["name"], "novo": True}


def _dimensoes(caminho: Path) -> tuple[int, int]:
    captura = cv2.VideoCapture(str(caminho))
    try:
        return int(captura.get(cv2.CAP_PROP_FRAME_WIDTH)), int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        captura.release()


def _guardar_landmarks(db, projeto, classe, sinalizante: str,
                       sequencia: np.ndarray, stats: dict) -> int:
    pasta = PROJECTS_DIR / projeto["slug"] / "sequences"
    pasta.mkdir(parents=True, exist_ok=True)
    cur = db.execute(
        """INSERT INTO examples (class_id, kind, source, filename, rel_path,
                                 size_bytes, signer_name)
           VALUES (?, 'video', 'webcam', '', '', 0, ?)""",
        (classe["id"], sinalizante))
    exemplo_id = cur.lastrowid
    npy = pasta / f"{exemplo_id}.npy"
    meta = pasta / f"{exemplo_id}.json"
    try:
        np.save(npy, sequencia)
        meta.write_text(json.dumps(stats), encoding="utf-8")
        db.execute(
            "UPDATE examples SET filename = ?, rel_path = ?, size_bytes = ? WHERE id = ?",
            (npy.name, npy.relative_to(PROJECTS_DIR).as_posix(),
             npy.stat().st_size, exemplo_id))
        touch_project(db, projeto["id"])
        db.commit()
    except Exception:
        db.rollback()
        npy.unlink(missing_ok=True)
        meta.unlink(missing_ok=True)
        raise
    return exemplo_id


@router.post("/gravacoes", status_code=201)
def gravar(sinal_id: int = Form(...), sinalizante: str = Form(...),
           video: UploadFile = File(...),
           db: sqlite3.Connection = Depends(get_db)):
    # def (não async): a extração é CPU pesada e roda no threadpool, sem
    # travar o servidor para quem estiver usando o admin.
    from vision import video as video_mod

    projeto, _ = _projeto(db)
    sinalizante = " ".join(sinalizante.split())[:40]
    if not sinalizante:
        raise HTTPException(400, "Informe quem gravou.")
    classe = db.execute("SELECT * FROM classes WHERE id = ? AND project_id = ?",
                        (sinal_id, projeto["id"])).fetchone()
    if classe is None:
        raise HTTPException(404, "Sinal não encontrado neste projeto.")

    sufixo = Path(video.filename or "").suffix.lower()
    if sufixo not in (".webm", ".mp4"):
        sufixo = ".webm"
    with tempfile.NamedTemporaryFile(suffix=sufixo, delete=False) as destino:
        temporario = Path(destino.name)
        shutil.copyfileobj(video.file, destino, length=1 << 20)
    try:
        if temporario.stat().st_size > MAX_BYTES:
            raise HTTPException(413, "Vídeo grande demais; grave até 4 segundos.")
        largura, altura = _dimensoes(temporario)
        if not largura or not altura:
            raise HTTPException(422, "Não consegui abrir o vídeo.")
        if abs(largura / altura - PROPORCAO) > 0.02:
            raise HTTPException(
                422, f"O vídeo veio {largura}×{altura}. Grave pelo app, que "
                     "enquadra em 640×480 como a webcam do KONECTA.")
        sequencia, stats = video_mod.extract_sequence_from_file(temporario)
        if sequencia is None:
            raise HTTPException(422, "Não consegui ler os quadros do vídeo.")
        if stats["quality"] < QUALIDADE_MINIMA:
            raise HTTPException(
                422, f"As mãos apareceram em só {stats['quality']:.0%} do vídeo. "
                     "Grave de novo com as mãos inteiras no quadro e boa luz.")
        exemplo_id = _guardar_landmarks(db, projeto, classe, sinalizante,
                                        sequencia, stats)
    finally:
        # O vídeo nunca é guardado: só a posição das mãos fica.
        temporario.unlink(missing_ok=True)

    meus, total = _contagem(db, classe["id"], sinalizante)
    return {"id": exemplo_id, "qualidade": stats["quality"],
            "meus": meus, "total": total}

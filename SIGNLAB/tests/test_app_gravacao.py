"""App de gravação: acesso, landmarks sem vídeo e publicação automática.

Roda num banco e numa pasta de projetos temporários — as variáveis de
ambiente precisam valer antes de importar o app.

    python -m pytest tests/test_app_gravacao.py -q
"""
import atexit
import glob
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="signlab_teste_"))
# Guarda landmarks derivados de gravações reais: não pode sobrar no disco,
# nem quando a execução é filtrada com -k ou cai no meio.
atexit.register(shutil.rmtree, TMP, ignore_errors=True)
os.environ["SIGNLAB_DB"] = str(TMP / "data" / "signlab.db")
os.environ["SIGNLAB_PROJECTS"] = str(TMP / "projects")
os.environ["SIGNLAB_SEM_PUBLICADOR"] = "1"
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient  # noqa: E402

from app.backend import acesso, publicador  # noqa: E402
from app.backend.main import app  # noqa: E402
from app.backend.routes import app_gravacao, training  # noqa: E402

# Uma gravação real que treinou o modelo que reconhece (640x480, mãos visíveis).
VIDEO_REAL = sorted(glob.glob(str(RAIZ / "projects" / "sinais-teste" / "videos" / "*" / "*.webm")))


def _video_sintetico(caminho: Path, largura: int, altura: int) -> Path:
    escritor = cv2.VideoWriter(str(caminho), cv2.VideoWriter_fourcc(*"mp4v"), 30, (largura, altura))
    for i in range(60):
        quadro = np.full((altura, largura, 3), 40 + i, np.uint8)  # sem mão nenhuma
        escritor.write(quadro)
    escritor.release()
    return caminho


@pytest.fixture(scope="module")
def cliente():
    # https: o cookie é Secure e o httpx não o devolve por http.
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def _entrar(cliente, papel):
    cliente.cookies.clear()
    r = cliente.post("/api/entrar", json={"codigo": acesso.codigos()[papel]})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def projeto(cliente):
    _entrar(cliente, "admin")
    pid = cliente.post("/api/projects", json={"name": "Coleta noiva"}).json()["id"]
    outro = cliente.post("/api/projects", json={"name": "Outro"}).json()["id"]
    sinal = cliente.post(f"/api/projects/{pid}/classes", json={"name": "Mãe"}).json()["id"]
    alheio = cliente.post(f"/api/projects/{outro}/classes", json={"name": "Pai"}).json()["id"]
    return {"id": pid, "sinal": sinal, "sinal_alheio": alheio}


# ---------- acesso ----------

def test_sem_login_nada_de_dados(cliente):
    cliente.cookies.clear()
    assert cliente.get("/api/projects").status_code == 401
    assert cliente.get("/app-api/estado").status_code == 401
    assert cliente.get("/files/qualquer.webm").status_code == 401
    assert cliente.get("/docs").status_code == 401
    r = cliente.get("/", headers={"accept": "text/html"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/entrar.html"


def test_casca_do_app_e_entrada_sao_abertas(cliente):
    cliente.cookies.clear()
    assert cliente.get("/entrar.html").status_code == 200
    r = cliente.get("/app/")
    assert r.status_code == 200 and "SIGNLAB" in r.text
    assert r.headers["cache-control"] == "no-cache"
    assert cliente.get("/app/manifest.webmanifest").status_code == 200


def test_codigo_errado(cliente):
    cliente.cookies.clear()
    assert cliente.post("/api/entrar", json={"codigo": "chute"}).status_code == 401


def test_papel_gravacao_nao_alcanca_o_admin(cliente, projeto):
    assert _entrar(cliente, "gravacao")["destino"] == "/app/"
    assert cliente.get("/api/projects").status_code == 403
    assert cliente.delete(f"/api/classes/{projeto['sinal']}").status_code == 403
    assert cliente.post(f"/api/projects/{projeto['id']}/train", json={"model_type": "bilstm"}).status_code == 403
    assert cliente.get("/files/qualquer.webm").status_code == 403
    r = cliente.get("/", headers={"accept": "text/html"}, follow_redirects=False)
    assert r.headers["location"] == "/app/"


def test_admin_nunca_recebe_js_velho_do_cache(cliente):
    _entrar(cliente, "admin")
    r = cliente.get("/js/app.js")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"


def test_codigo_trocado_para_de_valer(cliente):
    antigo = acesso.codigos()["gravacao"]
    acesso.trocar_codigo("gravacao")
    cliente.cookies.clear()
    assert cliente.post("/api/entrar", json={"codigo": antigo}).status_code == 401


# ---------- app ----------

def test_sem_configuracao_responde_503(cliente, projeto):
    _entrar(cliente, "gravacao")
    app_gravacao.CONFIG.unlink(missing_ok=True)
    assert cliente.get("/app-api/estado").status_code == 503


def test_criar_sinal_nao_duplica_por_maiusculas(cliente, projeto):
    app_gravacao.salvar_config(projeto_id=projeto["id"])
    _entrar(cliente, "gravacao")
    r = cliente.post("/app-api/sinais", json={"nome": "  MÃE  "})
    assert r.status_code == 200 and r.json() == {"id": projeto["sinal"], "nome": "Mãe", "novo": False}
    r = cliente.post("/app-api/sinais", json={"nome": "Filha"})
    assert r.status_code == 201 and r.json()["novo"] is True


@pytest.mark.skipif(not VIDEO_REAL, reason="sem gravação real em projects/sinais-teste")
def test_gravacao_guarda_so_landmarks(cliente, projeto, monkeypatch):
    app_gravacao.salvar_config(projeto_id=projeto["id"])
    _entrar(cliente, "gravacao")
    # O vídeo passa por um arquivo temporário; aponta o temp para uma pasta
    # própria para provar que ele não sobra lá (a promessa feita a ela no app).
    temporarios = TMP / "temporarios"
    temporarios.mkdir(exist_ok=True)
    monkeypatch.setattr(tempfile, "tempdir", str(temporarios))
    with open(VIDEO_REAL[0], "rb") as f:
        r = cliente.post("/app-api/gravacoes",
                         data={"sinal_id": projeto["sinal"], "sinalizante": " Ana  Paula "},
                         files={"video": ("gravacao.webm", f, "video/webm")})
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["meus"] == 1 and corpo["qualidade"] >= 0.25

    db = sqlite3.connect(os.environ["SIGNLAB_DB"])
    db.row_factory = sqlite3.Row
    ex = db.execute("SELECT * FROM examples WHERE id = ?", (corpo["id"],)).fetchone()
    assert ex["signer_name"] == "Ana Paula"
    assert ex["rel_path"].endswith(f"sequences/{corpo['id']}.npy")

    projetos = Path(os.environ["SIGNLAB_PROJECTS"])
    assert np.load(projetos / ex["rel_path"]).shape == (30, 128)
    # nenhum vídeo ficou: nem no projeto, nem no temporário
    assert not [p for p in projetos.rglob("*") if p.suffix in (".webm", ".mp4")]
    assert not list(temporarios.iterdir())

    # o treino lê o .npy direto, sem tentar abrir vídeo
    slug = db.execute("SELECT slug FROM projects WHERE id = ?", (projeto["id"],)).fetchone()[0]
    seq, stats = training.sequence_for_example(dict(ex), slug, 30)
    assert seq.shape == (30, 128) and stats["quality"] >= 0.25

    estado = cliente.get("/app-api/estado", params={"sinalizante": "Ana Paula"}).json()
    mae = next(s for s in estado["sinais"] if s["id"] == projeto["sinal"])
    assert mae["meus"] == 1

    # excluir no admin apaga os landmarks junto
    _entrar(cliente, "admin")
    assert cliente.delete(f"/api/examples/{corpo['id']}").status_code == 204
    assert not (projetos / ex["rel_path"]).exists()


def test_recusa_video_em_pe(cliente, projeto):
    app_gravacao.salvar_config(projeto_id=projeto["id"])
    _entrar(cliente, "gravacao")
    video = _video_sintetico(TMP / "em_pe.mp4", 480, 640)
    with open(video, "rb") as f:
        r = cliente.post("/app-api/gravacoes", data={"sinal_id": projeto["sinal"], "sinalizante": "Ana"},
                         files={"video": ("g.mp4", f, "video/mp4")})
    assert r.status_code == 422 and "640×480" in r.json()["detail"]


def test_recusa_video_sem_maos(cliente, projeto):
    app_gravacao.salvar_config(projeto_id=projeto["id"])
    _entrar(cliente, "gravacao")
    video = _video_sintetico(TMP / "sem_maos.mp4", 640, 480)
    antes = len(list(Path(os.environ["SIGNLAB_PROJECTS"]).rglob("*.npy")))
    with open(video, "rb") as f:
        r = cliente.post("/app-api/gravacoes", data={"sinal_id": projeto["sinal"], "sinalizante": "Ana"},
                         files={"video": ("g.mp4", f, "video/mp4")})
    assert r.status_code == 422 and "mãos" in r.json()["detail"]
    assert len(list(Path(os.environ["SIGNLAB_PROJECTS"]).rglob("*.npy"))) == antes


def test_nao_grava_em_sinal_de_outro_projeto(cliente, projeto):
    app_gravacao.salvar_config(projeto_id=projeto["id"])
    _entrar(cliente, "gravacao")
    video = _video_sintetico(TMP / "qualquer.mp4", 640, 480)
    with open(video, "rb") as f:
        r = cliente.post("/app-api/gravacoes", data={"sinal_id": projeto["sinal_alheio"], "sinalizante": "Ana"},
                         files={"video": ("g.mp4", f, "video/mp4")})
    assert r.status_code == 404


# ---------- publicação automática ----------

def _exemplo_novo(pid):
    db = sqlite3.connect(os.environ["SIGNLAB_DB"])
    cid = db.execute("SELECT id FROM classes WHERE project_id = ? LIMIT 1", (pid,)).fetchone()[0]
    cur = db.execute(
        """INSERT INTO examples (class_id, kind, source, filename, rel_path, signer_name, created_at)
           VALUES (?, 'video', 'webcam', 'x.npy', 'x.npy', 'Ana', datetime('now', '-1 hour'))""", (cid,))
    db.commit()
    return cur.lastrowid


def _experimento(pid, acuracia):
    db = sqlite3.connect(os.environ["SIGNLAB_DB"])
    cur = db.execute(
        "INSERT INTO experiments (project_id, model_type, metrics, classes) VALUES (?, 'bilstm', ?, ?)",
        (pid, json.dumps({"accuracy": acuracia}), json.dumps([{"name": "Mãe"}, {"name": "Filha"}])))
    db.commit()
    return cur.lastrowid


def test_publicador(projeto, monkeypatch):
    pid = projeto["id"]
    app_gravacao.salvar_config(projeto_id=pid, espera_s=0, acuracia_minima=0.6)
    app_gravacao.ESTADO.unlink(missing_ok=True)
    treinos = []

    def treino_falso(acuracia):
        def _t(projeto_id, modelo):
            treinos.append(projeto_id)
            return {"state": "done", "experiment_id": _experimento(pid, acuracia)}
        return _t

    # abaixo do mínimo: não publica, e não retreina o mesmo dado de novo
    ultimo = _exemplo_novo(pid)
    monkeypatch.setattr(publicador, "_treinar", treino_falso(0.4))
    monkeypatch.setattr(publicador, "_publicar", lambda *a: pytest.fail("não devia publicar"))
    publicador.ciclo()
    estado = app_gravacao.ler_estado()
    assert estado["estado"] == "retido" and estado["publicado_ate"] == ultimo
    publicador.ciclo()
    assert len(treinos) == 1

    # acima do mínimo: publica
    ultimo = _exemplo_novo(pid)
    monkeypatch.setattr(publicador, "_treinar", treino_falso(0.9))
    monkeypatch.setattr(publicador, "_publicar", lambda db, e, slug, destino: Path("m.zip"))
    publicador.ciclo()
    estado = app_gravacao.ler_estado()
    assert estado["estado"] == "publicado" and estado["sinais"] == 2 and estado["arquivo"] == "m.zip"

    # falha na cópia: registra o erro e não entra em laço de retreino
    ultimo = _exemplo_novo(pid)

    def copia_quebrada(*a):
        raise OSError("disco cheio")
    monkeypatch.setattr(publicador, "_publicar", copia_quebrada)
    publicador.ciclo()
    estado = app_gravacao.ler_estado()
    assert estado["estado"] == "erro" and "disco cheio" in estado["mensagem"]
    assert estado["publicado_ate"] == ultimo
    n = len(treinos)
    publicador.ciclo()
    assert len(treinos) == n

    # ainda gravando: espera
    app_gravacao.salvar_config(espera_s=10_000)
    _exemplo_novo(pid)
    publicador.ciclo()
    assert len(treinos) == n

"""Publica no KONECTA, sozinho, o que chega pelo app de gravação.

Quando as gravações do projeto do app param de chegar por ``espera_s``
segundos, treina com o mesmo job do botão "Treinar" do admin, gera o .zip do
export e o larga em ``KONECTA_V3/models/``, onde o KONECTA troca de modelo a
quente.

Um modelo abaixo de ``acuracia_minima`` não é publicado e o KONECTA segue com
o anterior: publicar às cegas trocaria um modelo que reconhece por um pior sem
ninguém perceber.
"""
import json
import logging
import os
import shutil
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .database import DB_PATH
from .routes import app_gravacao, training

logger = logging.getLogger("signlab.publicador")

INTERVALO_S = 20


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _segundos_desde(sqlite_utc: str) -> float:
    quando = datetime.strptime(sqlite_utc, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - quando).total_seconds()


def _treinar(projeto_id: int, modelo: str) -> dict:
    """Roda o job de treino na thread atual; devolve o estado final do job."""
    from lsae.pipeline import LsaeConfig

    with training.JOBS_LOCK:
        job = training.JOBS.get(projeto_id)
        if job and job["state"] in ("extracting", "training"):
            return {"state": "ocupado"}
        training.JOBS[projeto_id] = {"state": "extracting", "done": 0, "total": 0,
                                     "message": None, "experiment_id": None}
    # LSAE desligado (o padrão do LsaeConfig): nas medições do V-LIBRASIL o
    # aumento sintético piorou o cross-signer em vez de ajudar.
    training.run_training(projeto_id, modelo, LsaeConfig(), False)
    return training.JOBS[projeto_id]


def _publicar(db, experimento_id: int, slug: str, destino: Path) -> Path:
    zip_origem = training.build_export_zip(db, experimento_id)
    destino.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d-%H%M")
    # Projeto e data no nome: o id do experimento recomeça se o banco for
    # recriado (já aconteceu) e sobrescreveria um modelo antigo.
    final = destino / f"signlab_{slug}_exp{experimento_id}_{carimbo}.zip"
    # Copia com outro nome e renomeia: o KONECTA procura *.zip a cada 10s e
    # não pode pegar um arquivo pela metade.
    parcial = final.with_name(final.name + ".parcial")
    shutil.copy2(zip_origem, parcial)
    os.replace(parcial, final)
    return final


def ciclo() -> None:
    """Uma passada: decide se há o que publicar e publica."""
    cfg = app_gravacao.ler_config()
    if not cfg["projeto_id"]:
        return
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    try:
        projeto = db.execute("SELECT * FROM projects WHERE id = ?",
                             (cfg["projeto_id"],)).fetchone()
        if projeto is None:
            return
        ultimo, quando = db.execute(
            """SELECT MAX(e.id), MAX(e.created_at) FROM examples e
               JOIN classes c ON c.id = e.class_id WHERE c.project_id = ?""",
            (projeto["id"],)).fetchone()
        estado = app_gravacao.ler_estado()
        if not ultimo or ultimo <= estado.get("publicado_ate", 0):
            return
        if _segundos_desde(quando) < cfg["espera_s"]:
            return  # ela ainda está gravando

        app_gravacao.salvar_estado(estado="treinando", quando=_agora(), mensagem=None)
        try:
            _treinar_e_publicar(db, projeto, cfg, ultimo, estado)
        except Exception as erro:  # noqa: BLE001
            # Sem marcar publicado_ate, uma falha deterministica (pasta de
            # destino invalida, disco cheio) retreinaria a cada 20s para sempre.
            logger.exception("Publicação automática falhou")
            app_gravacao.salvar_estado(publicado_ate=ultimo, estado="erro",
                                       quando=_agora(), mensagem=f"Erro inesperado: {erro}")
    finally:
        db.close()


def _treinar_e_publicar(db, projeto, cfg: dict, ultimo: int, estado: dict) -> None:
    job = _treinar(projeto["id"], cfg["modelo"])
    if job["state"] == "ocupado":
        app_gravacao.salvar_estado(estado=estado.get("estado", "ocioso"))
        return  # alguém treinou pelo admin; tenta de novo no próximo ciclo

    # Marca como tratado mesmo se falhar: o mesmo dado falharia de novo a
    # cada 20s. A próxima gravação dispara outra tentativa.
    if job["state"] != "done":
        app_gravacao.salvar_estado(publicado_ate=ultimo, estado="erro",
                                   quando=_agora(), mensagem=job.get("message"))
        return

    experimento_id = job["experiment_id"]
    linha = db.execute("SELECT metrics, classes FROM experiments WHERE id = ?",
                       (experimento_id,)).fetchone()
    metricas = json.loads(linha["metrics"])
    acuracia = float(metricas.get("accuracy", 0.0))
    n_sinais = sum(1 for c in json.loads(linha["classes"]) if not c.get("excluded"))
    comum = dict(publicado_ate=ultimo, quando=_agora(), experimento=experimento_id,
                 acuracia=round(acuracia, 4), sinais=n_sinais)

    if acuracia < cfg["acuracia_minima"]:
        app_gravacao.salvar_estado(
            **comum, estado="retido",
            mensagem=f"acurácia {acuracia:.0%}, abaixo do mínimo de "
                     f"{cfg['acuracia_minima']:.0%}; o KONECTA segue com o modelo anterior")
        logger.warning("Experimento %s retido: acurácia %.2f", experimento_id, acuracia)
        return

    arquivo = _publicar(db, experimento_id, projeto["slug"], Path(cfg["publicar_em"]))
    app_gravacao.salvar_estado(**comum, estado="publicado", arquivo=arquivo.name,
                               mensagem=None)
    logger.info("Publicado no KONECTA: %s (%d sinais, acurácia %.2f)",
                arquivo.name, n_sinais, acuracia)


def _laco() -> None:
    while True:
        try:
            ciclo()
        except Exception:  # noqa: BLE001 — a thread não pode morrer calada
            logger.exception("Publicador: falha ao verificar o projeto")
        time.sleep(INTERVALO_S)


def iniciar() -> None:
    if os.environ.get("SIGNLAB_SEM_PUBLICADOR"):
        return
    threading.Thread(target=_laco, name="publicador", daemon=True).start()

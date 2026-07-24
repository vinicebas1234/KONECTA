#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          CONVERSOR DE VÍDEOS VLibrasil → SEQUÊNCIAS .npy                   ║
║     Compatível com o modelo LSTM do libras_recognizer.py (TCC)             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Uso:                                                                       ║
║    python vlibrasil_converter.py                                            ║
║                                                                             ║
║  Configure os caminhos na seção CONFIGURAÇÕES abaixo antes de rodar.       ║
╚══════════════════════════════════════════════════════════════════════════════╝

O que o script faz:
  1. Varre VLIBRASIL_DIR buscando subpastas (cada uma = um sinal).
  2. Para cada vídeo dentro da subpasta, amostra SEQUENCE_LENGTH frames
     uniformemente distribuídos ao longo do vídeo.
  3. Roda o MediaPipe HandLandmarker em cada frame e extrai o vetor de
     features de 126 dimensões (21 landmarks × 3 coords × 2 mãos) —
     exatamente a mesma normalização do DetectorMaos do app.
  4. Salva a sequência em:
       <PROJETO_DIR>/dados_libras/dinamicos/<sinal>/public/public_XXXX.npy
     — formato idêntico ao usado pelo GerenciadorDados, com origem "public".
  5. Pula vídeos já convertidos (retoma de onde parou se interrompido).
  6. Pula vídeos onde o MediaPipe detectou mão em menos de MIN_MAO_FRAMES
     dos 30 frames (vídeo provavelmente sem mãos visíveis).
  7. Gera um relatório final com contagens por sinal.
"""

import csv
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÕES — edite aqui antes de rodar
# ──────────────────────────────────────────────────────────────────────────────

# Pasta raiz do dataset VLibrasil (onde estão as subpastas de cada sinal)
VLIBRASIL_DIR = Path(r"C:\KONECTA\Datasets\videos UFPE (V-LIBRASIL)\data")

# Pasta raiz do seu projeto (onde está o libras_recognizer.py)
PROJETO_DIR = Path(r"C:\KONECTA\OCR")

# Arquivo hand_landmarker.task — gerado automaticamente pelo app ao iniciar,
# ou baixe de: https://storage.googleapis.com/mediapipe-models/hand_landmarker/
#              hand_landmarker/float16/1/hand_landmarker.task
HAND_TASK_FILE = PROJETO_DIR / "modelos" / "hand_landmarker.task"

# ──────────────────────────────────────────────────────────────────────────────
# PARÂMETROS (mesmos valores do libras_recognizer.py)
# ──────────────────────────────────────────────────────────────────────────────

SEQUENCE_LENGTH   = 30          # frames por sequência
TOTAL_FEATURES    = 126         # 21 landmarks × 3 coords × 2 mãos
FEATURES_PER_HAND = 63          # 21 × 3
MAX_HANDS         = 2
MIN_MAO_FRAMES    = 8           # descarta vídeo se menos que isso tiver mão
MP_DET_CONF       = 0.5         # confiança de detecção (levemente menor que
MP_TRK_CONF       = 0.5         # o app para ser mais permissivo com o dataset)

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".mpg", ".mpeg"}

# ──────────────────────────────────────────────────────────────────────────────
# SAÍDA
# ──────────────────────────────────────────────────────────────────────────────

DIR_DINAMICOS = PROJETO_DIR / "dados_libras" / "dinamicos"
LOG_FILE      = PROJETO_DIR / f"vlibrasil_converter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"


# ══════════════════════════════════════════════════════════════════════════════
# MEDIAPIPE — inicialização
# ══════════════════════════════════════════════════════════════════════════════

def _criar_detector(task_path: Path):
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    if not task_path.exists():
        raise FileNotFoundError(
            f"Arquivo hand_landmarker.task não encontrado em:\n  {task_path}\n\n"
            "Abra o libras_recognizer.py uma vez para que ele baixe automaticamente,\n"
            "ou baixe manualmente de:\n"
            "  https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
            "hand_landmarker/float16/1/hand_landmarker.task"
        )

    base_options = mp_python.BaseOptions(model_asset_path=str(task_path))
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.IMAGE,
        num_hands=MAX_HANDS,
        min_hand_detection_confidence=MP_DET_CONF,
        min_tracking_confidence=MP_TRK_CONF,
    )
    return vision.HandLandmarker.create_from_options(options)


# ══════════════════════════════════════════════════════════════════════════════
# EXTRAÇÃO DE FEATURES — idêntica ao DetectorMaos.extrair_features()
# ══════════════════════════════════════════════════════════════════════════════

def _normalizar_mao(pts: np.ndarray) -> np.ndarray:
    """Centraliza no pulso (landmark 0) e normaliza pela distância pulso→dedo médio base."""
    pts = pts.astype(np.float32).copy()
    center = pts[0].copy()
    pts -= center
    ref = np.linalg.norm(pts[9] - pts[0])
    if ref < 1e-6:
        ref = np.max(np.abs(pts))
    if ref < 1e-6:
        ref = 1.0
    pts /= float(ref)
    pts = np.clip(pts, -3.0, 3.0)
    return pts


def extrair_features(result) -> np.ndarray:
    """Retorna vetor float32 de tamanho 126. Zeros onde não há mão detectada."""
    feats = np.zeros(TOTAL_FEATURES, dtype=np.float32)
    if not result.hand_landmarks:
        return feats
    for idx, hand in enumerate(result.hand_landmarks):
        if idx >= MAX_HANDS:
            break
        pts = np.array([[lm.x, lm.y, lm.z] for lm in hand], dtype=np.float32)
        pts = _normalizar_mao(pts)
        start = idx * FEATURES_PER_HAND
        feats[start : start + FEATURES_PER_HAND] = pts.flatten()
    return feats


# ══════════════════════════════════════════════════════════════════════════════
# PROCESSAMENTO DE VÍDEO
# ══════════════════════════════════════════════════════════════════════════════

def _amostrar_indices(total_frames: int, n: int = SEQUENCE_LENGTH) -> list[int]:
    """Retorna n índices uniformemente distribuídos ao longo do vídeo."""
    if total_frames <= 0:
        return []
    return list(np.linspace(0, total_frames - 1, min(n, total_frames), dtype=int))


def processar_video(caminho: Path, detector) -> tuple[np.ndarray | None, str]:
    """
    Extrai uma sequência (SEQUENCE_LENGTH, 126) do vídeo.

    Retorna:
        (sequencia, status)  onde status é "ok", "sem_mao" ou "erro:<mensagem>"
    """
    try:
        import mediapipe as mp

        cap = cv2.VideoCapture(str(caminho))
        if not cap.isOpened():
            return None, f"erro:não foi possível abrir o arquivo"

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total < 1:
            cap.release()
            return None, "erro:vídeo sem frames"

        indices = _amostrar_indices(total, SEQUENCE_LENGTH)
        seq = []

        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, float(idx))
            ok, frame = cap.read()
            if not ok:
                # frame ilegível: usa zeros
                seq.append(np.zeros(TOTAL_FEATURES, dtype=np.float32))
                continue

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            result = detector.detect(mp_image)
            seq.append(extrair_features(result))

        cap.release()

        if len(seq) == 0:
            return None, "erro:nenhum frame lido"

        # Padding se o vídeo tiver menos frames que SEQUENCE_LENGTH
        while len(seq) < SEQUENCE_LENGTH:
            seq.append(seq[-1].copy())

        seq_arr = np.array(seq[:SEQUENCE_LENGTH], dtype=np.float32)

        # Descarta vídeo onde mãos quase nunca aparecem
        frames_com_mao = int(np.sum(np.any(seq_arr != 0, axis=1)))
        if frames_com_mao < MIN_MAO_FRAMES:
            return None, f"sem_mao:{frames_com_mao}/{SEQUENCE_LENGTH} frames com mão"

        return seq_arr, "ok"

    except Exception as exc:
        return None, f"erro:{exc}"


# ══════════════════════════════════════════════════════════════════════════════
# UTILITÁRIOS DE PROGRESSO
# ══════════════════════════════════════════════════════════════════════════════

def _barra(atual, total, largura=40):
    frac = atual / max(total, 1)
    cheio = int(frac * largura)
    return f"[{'█' * cheio}{'░' * (largura - cheio)}] {atual}/{total} ({frac:.0%})"


class _Progresso:
    def __init__(self, total):
        self.total = total
        self.atual = 0
        self.t0 = time.time()

    def atualizar(self, rotulo, status):
        self.atual += 1
        elapsed = time.time() - self.t0
        eta = (elapsed / self.atual) * (self.total - self.atual) if self.atual else 0
        print(
            f"\r{_barra(self.atual, self.total)}  "
            f"ETA {eta/60:.1f}min  [{rotulo[:20]:<20}] {status:<30}",
            end="",
            flush=True,
        )

    def finalizar(self):
        print()  # nova linha após a barra


# ══════════════════════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def main():
    # ── validações iniciais ──────────────────────────────────────────────────
    if not VLIBRASIL_DIR.exists():
        print(f"❌ VLIBRASIL_DIR não encontrado: {VLIBRASIL_DIR}")
        print("   Edite a variável VLIBRASIL_DIR no topo do script.")
        sys.exit(1)

    if not HAND_TASK_FILE.exists():
        print(f"❌ hand_landmarker.task não encontrado: {HAND_TASK_FILE}")
        print("   Abra o libras_recognizer.py uma vez para baixar automaticamente.")
        sys.exit(1)

    DIR_DINAMICOS.mkdir(parents=True, exist_ok=True)

    # ── levantamento dos vídeos ──────────────────────────────────────────────
    print("🔍 Varrendo dataset VLibrasil...")
    tarefas: list[tuple[str, Path]] = []  # (rotulo, caminho_video)

    for pasta_sinal in sorted(VLIBRASIL_DIR.iterdir()):
        if not pasta_sinal.is_dir():
            continue
        rotulo = pasta_sinal.name
        for arquivo in sorted(pasta_sinal.iterdir()):
            if arquivo.suffix.lower() in VIDEO_EXTS:
                tarefas.append((rotulo, arquivo))

    if not tarefas:
        print("❌ Nenhum vídeo encontrado. Verifique o caminho e as extensões suportadas.")
        sys.exit(1)

    # ── verifica quais já foram convertidos (para retomar) ───────────────────
    pendentes = []
    ja_feitos = 0
    for rotulo, vid in tarefas:
        pasta_saida = DIR_DINAMICOS / rotulo / "public"
        # Usa o nome do vídeo como marcador (arquivo .npy correspondente)
        marcador = pasta_saida / f"{vid.stem}.npy.done"
        if marcador.exists():
            ja_feitos += 1
        else:
            pendentes.append((rotulo, vid, pasta_saida))

    total_vid = len(tarefas)
    total_pend = len(pendentes)
    print(f"📦 Total de vídeos: {total_vid}  |  Já convertidos: {ja_feitos}  |  Pendentes: {total_pend}")

    if total_pend == 0:
        print("✅ Todos os vídeos já foram convertidos.")
        return

    # ── inicializa detector ──────────────────────────────────────────────────
    print(f"🚀 Inicializando MediaPipe HandLandmarker...")
    detector = _criar_detector(HAND_TASK_FILE)
    print("   OK")

    # ── processamento ────────────────────────────────────────────────────────
    print(f"\n⚙  Processando {total_pend} vídeos...")

    contadores = {"ok": 0, "sem_mao": 0, "erro": 0}
    log_linhas = [["rotulo", "arquivo", "status", "destino"]]
    prog = _Progresso(total_pend)

    for rotulo, vid, pasta_saida in pendentes:
        pasta_saida.mkdir(parents=True, exist_ok=True)

        seq, status = processar_video(vid, detector)

        if status == "ok" and seq is not None:
            # determina índice do próximo arquivo
            existentes = sorted(pasta_saida.glob("public_*.npy"))
            proximo = len(existentes)
            dest = pasta_saida / f"public_{proximo:04d}.npy"
            np.save(dest, seq)
            # cria marcador de "já feito" com o nome do vídeo
            (pasta_saida / f"{vid.stem}.npy.done").touch()
            contadores["ok"] += 1
            log_linhas.append([rotulo, vid.name, "ok", str(dest)])
        elif status.startswith("sem_mao"):
            contadores["sem_mao"] += 1
            (pasta_saida / f"{vid.stem}.npy.done").touch()  # marca como tentado
            log_linhas.append([rotulo, vid.name, status, ""])
        else:
            contadores["erro"] += 1
            log_linhas.append([rotulo, vid.name, status, ""])

        prog.atualizar(rotulo, status)

    prog.finalizar()
    detector.close()

    # ── relatório ────────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print("✅  CONVERSÃO CONCLUÍDA")
    print(f"   Convertidos com sucesso : {contadores['ok']}")
    print(f"   Descartados (sem mão)   : {contadores['sem_mao']}")
    print(f"   Erros                   : {contadores['erro']}")

    # contagem por sinal
    sinais_count: dict[str, int] = {}
    for rotulo, vid, pasta_saida in pendentes:
        npy_count = len(list(pasta_saida.glob("public_*.npy")))
        sinais_count[rotulo] = npy_count

    top = sorted(sinais_count.items(), key=lambda x: x[1], reverse=True)
    print(f"\n   Sinais com mais amostras (top 10):")
    for nome, qtd in top[:10]:
        print(f"     {qtd:3d}x  {nome}")

    # salva CSV de log
    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(log_linhas)
    print(f"\n   Log salvo em: {LOG_FILE}")
    print("═" * 60)
    print("\n💡 Próximo passo: abra o libras_recognizer.py e clique em")
    print("   '🏋 Treinar Dinâmico' — o app encontrará os novos arquivos")
    print("   automaticamente em dados_libras/dinamicos/.")


if __name__ == "__main__":
    main()

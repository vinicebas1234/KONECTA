"""Extração de sequências temporais de vídeos.

Pipeline: vídeo → decoder → amostragem uniforme de frames →
landmarks por frame (MediaPipe) → features normalizadas →
sequência (seq_len, 128) com normalização temporal.

Frames sem mão detectada viram vetor zero (flags de presença = 0);
a fração de frames com mão vira o indicador de qualidade da sequência.
A leitura é sempre sequencial (sem seek), o que funciona tanto para
mp4 quanto para webm gravado pelo MediaRecorder (que não reporta
frame count nem aceita seek).
"""
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

from . import hands
from .features import FEATURE_LENGTH, feature_vector

DEFAULT_SEQUENCE_LENGTH = 30
MAX_DECODE_FRAMES = 5400  # ~3 min a 30fps; evita vídeos absurdamente longos


def _count_frames(path: str) -> tuple[int, float]:
    """Conta frames decodificando (metadados de webm mentem ou faltam)."""
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    n = 0
    while n < MAX_DECODE_FRAMES:
        ok = cap.grab()
        if not ok:
            break
        n += 1
    cap.release()
    return n, fps


def extract_sequence_from_file(path, seq_len: int = DEFAULT_SEQUENCE_LENGTH):
    """Retorna (sequência (seq_len, 128) float32, stats) ou (None, None)."""
    path = str(path)
    started = time.time()
    total, fps = _count_frames(path)
    if total == 0:
        return None, None

    # amostragem uniforme; vídeos curtos repetem frames (normalização temporal)
    indices = np.linspace(0, total - 1, seq_len).round().astype(int)
    wanted = {}
    cap = cv2.VideoCapture(path)
    frame_idx = 0
    unique = set(indices.tolist())
    while frame_idx < total and unique:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx in unique:
            unique.discard(frame_idx)
            landmarks = hands.extract_from_bgr(frame)
            wanted[frame_idx] = feature_vector(landmarks)
        frame_idx += 1
    cap.release()

    sequence = []
    with_hands = 0
    for idx in indices:
        vec = wanted.get(int(idx))
        if vec is None:
            vec = np.zeros(FEATURE_LENGTH, dtype=np.float32)
        else:
            with_hands += 1
        sequence.append(vec)

    stats = {
        "frames_total": int(total),
        "frames_sampled": int(seq_len),
        "frames_with_hands": int(with_hands),
        "quality": round(with_hands / seq_len, 4),
        "fps": round(float(fps), 1),
        "duration_s": round(total / fps, 2) if fps else None,
        "process_seconds": round(time.time() - started, 2),
    }
    return np.stack(sequence), stats


def extract_sequence_from_bytes(data: bytes, filename: str = "video.mp4",
                                seq_len: int = DEFAULT_SEQUENCE_LENGTH):
    """Grava os bytes em arquivo temporário e extrai a sequência."""
    suffix = Path(filename).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        return extract_sequence_from_file(tmp_path, seq_len)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

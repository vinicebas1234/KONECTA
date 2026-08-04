"""Extração de landmarks de mãos com MediaPipe HandLandmarker (Tasks API).

O modelo hand_landmarker.task fica em vision/models/. O landmarker não é
thread-safe: todo detect() passa por um Lock único. O import do mediapipe
é lazy (demora alguns segundos) para não atrasar o startup do servidor.
"""
import threading
from pathlib import Path

import cv2
import numpy as np

MODEL_PATH = Path(__file__).parent / "models" / "hand_landmarker.task"

_landmarker = None
_lock = threading.Lock()


def _get_landmarker():
    global _landmarker
    if _landmarker is None:
        import mediapipe as mp
        from mediapipe.tasks.python import vision as mp_vision
        from mediapipe.tasks.python.core.base_options import BaseOptions

        if not MODEL_PATH.is_file():
            raise FileNotFoundError(
                f"Modelo do MediaPipe não encontrado: {MODEL_PATH}")
        _landmarker = mp_vision.HandLandmarker.create_from_options(
            mp_vision.HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
                running_mode=mp_vision.RunningMode.IMAGE,
                num_hands=2,
                min_hand_detection_confidence=0.5,
            ))
    return _landmarker


def extract_from_bgr(image_bgr: np.ndarray) -> dict:
    """Extrai landmarks das mãos de uma imagem BGR (formato OpenCV).

    Retorna {"left_hand": [[x,y,z]*21] | None, "right_hand": ... | None}.
    Coordenadas normalizadas pela resolução da imagem (padrão MediaPipe).
    """
    import mediapipe as mp

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    with _lock:
        result = _get_landmarker().detect(mp_image)

    out = {"left_hand": None, "right_hand": None}
    for hand_lm, handedness in zip(result.hand_landmarks, result.handedness):
        points = [[p.x, p.y, p.z] for p in hand_lm]
        label = handedness[0].category_name  # 'Left' | 'Right'
        key = "left_hand" if label == "Left" else "right_hand"
        if out[key] is None:
            out[key] = points
        elif out["left_hand"] is None:
            out["left_hand"] = points
        elif out["right_hand"] is None:
            out["right_hand"] = points
    return out


def extract_from_file(path) -> dict | None:
    """Extrai landmarks de um arquivo de imagem. None se não for legível."""
    data = np.fromfile(str(path), dtype=np.uint8)  # suporta acentos no caminho
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        return None
    return extract_from_bgr(image)


def extract_from_bytes(data: bytes) -> dict | None:
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return None
    return extract_from_bgr(image)

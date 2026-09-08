"""Ciclo 1 do Libras Learning Agent: extração real de landmarks de MÃO via MediaPipe.

Escopo deliberado: só `HandLandmarker` (mãos esquerda + direita). Pose e face
ficam para um ciclo futuro. Ver `hand_landmarks.py` para o porquê deste
módulo existir (a regressão que ele foi desenhado para não repetir está
documentada lá).
"""

from libras_learning_agent.vision.hand_landmarks import (
    HandDetection,
    HandExtractionResult,
    HandFrameLandmarks,
    ensure_hand_landmarker_model,
    extract_hand_landmarks,
)
from libras_learning_agent.vision.storage import save_hand_extraction, save_landmarks_file

__all__ = [
    "HandDetection",
    "HandExtractionResult",
    "HandFrameLandmarks",
    "ensure_hand_landmarker_model",
    "extract_hand_landmarks",
    "save_hand_extraction",
    "save_landmarks_file",
]

"""Ciclo 1 (mãos) + Ciclo 13 (pose) do Libras Learning Agent: extração real de
landmarks via MediaPipe.

Escopo deliberado de cada um: `HandLandmarker` (mãos esquerda + direita) e,
isolado dele, `PoseLandmarker` (33 pontos do corpo). Os dois extratores são
independentes e paralelos — nenhum é integrado ao pipeline de treino/DTW
(`ml/`) neste ciclo. Face fica para um ciclo futuro. Ver `hand_landmarks.py` e
`pose_landmarks.py` para o porquê de cada módulo existir.
"""

from libras_learning_agent.vision.hand_landmarks import (
    HandDetection,
    HandExtractionResult,
    HandFrameLandmarks,
    ensure_hand_landmarker_model,
    extract_hand_landmarks,
)
from libras_learning_agent.vision.pose_landmarks import (
    PoseDetection,
    PoseExtractionResult,
    PoseFrameLandmarks,
    ensure_pose_landmarker_model,
    extract_pose_landmarks,
)
from libras_learning_agent.vision.storage import save_hand_extraction, save_landmarks_file

__all__ = [
    "HandDetection",
    "HandExtractionResult",
    "HandFrameLandmarks",
    "ensure_hand_landmarker_model",
    "extract_hand_landmarks",
    "PoseDetection",
    "PoseExtractionResult",
    "PoseFrameLandmarks",
    "ensure_pose_landmarker_model",
    "extract_pose_landmarks",
    "save_hand_extraction",
    "save_landmarks_file",
]

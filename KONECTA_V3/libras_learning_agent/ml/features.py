"""Converte a extração real do Ciclo 1 (`vision/hand_landmarks.py`) num vetor
de 128 features por frame — o mesmo contrato já validado em produção neste
projeto por `app_central/providers/signlab_sinais.py` (não importado daqui,
por isolamento — só o layout é reaproveitado, documentado abaixo e também em
`KONECTA_V3/ANALISE_E_PLANO_GAUNTLET.md`, seção "2. Os formatos de feature
não conversavam"):

    vetor[0:63]    mão esquerda, xyz normalizado (21 pontos × 3)
    vetor[63:126]  mão direita, xyz normalizado (21 pontos × 3)
    vetor[126]     1.0 se a esquerda foi detectada, senão 0.0
    vetor[127]     1.0 se a direita foi detectada, senão 0.0

Normalização por mão: subtrai o punho (landmark 0, vira a origem) e divide
pela distância punho→MCP do dedo médio (landmark 9). Isso torna o vetor
invariante à posição da mão no quadro e à distância da câmera — sem isso a
"distância" DTW mediria onde a pessoa estava sentada, não o gesto que fez.
"""

from __future__ import annotations

import numpy as np

from libras_learning_agent.vision.hand_landmarks import HandDetection, HandExtractionResult

VECTOR_SIZE = 128
_WRIST = 0
_MIDDLE_MCP = 9


def _normalize_hand(hand: HandDetection) -> np.ndarray:
    """21 pontos (x,y,z) -> vetor de 63, punho na origem, escala pelo MCP médio."""
    points = np.asarray(hand.points, dtype=np.float32)  # (21, 3)
    points = points - points[_WRIST]
    scale = float(np.linalg.norm(points[_MIDDLE_MCP]))
    if scale > 1e-6:
        points = points / scale
    return points.reshape(-1)


def normalize_hand_landmarks(result: HandExtractionResult) -> np.ndarray:
    """`HandExtractionResult` -> sequência (T, 128), T = número de frames.

    Frame sem a mão esquerda/direita detectada: a metade correspondente do
    vetor fica zerada e o flag de presença fica 0.0 — igual ao contrato do
    SIGNLAB, não é "detectei zero", é "não detectei".
    """
    sequence = np.zeros((result.frame_count, VECTOR_SIZE), dtype=np.float32)
    for t, frame in enumerate(result.frames):
        for hand in frame.hands:
            if hand.label == "Left":
                sequence[t, 0:63] = _normalize_hand(hand)
                sequence[t, 126] = 1.0
            elif hand.label == "Right":
                sequence[t, 63:126] = _normalize_hand(hand)
                sequence[t, 127] = 1.0
    return sequence

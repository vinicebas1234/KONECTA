"""Feature engineering sobre landmarks de mãos (Modo A — posição normalizada).

Normalização por mão: punho na origem, escala pela distância
punho → base do dedo médio (MCP). Reduz diferenças de posição na
imagem e de tamanho de mão entre sinalizantes.

Vetor final (128): mão esquerda (63) + mão direita (63) + 2 flags de presença.
"""
import numpy as np

FEATURE_LENGTH = 128

FEATURE_CONFIG = {
    "source": "mediapipe_hands",
    "mode": "A-position",
    "hands": 2,
    "points_per_hand": 21,
    "normalization": "wrist_origin__scale_wrist_to_middle_mcp",
    "layout": ["left_hand_xyz[63]", "right_hand_xyz[63]",
               "left_present", "right_present"],
    "length": FEATURE_LENGTH,
}

_WRIST = 0
_MIDDLE_MCP = 9


def normalize_hand(points) -> np.ndarray:
    """21 pontos [x,y,z] -> vetor 63 normalizado."""
    arr = np.asarray(points, dtype=np.float32)
    arr = arr - arr[_WRIST]
    scale = float(np.linalg.norm(arr[_MIDDLE_MCP]))
    if scale > 1e-6:
        arr = arr / scale
    return arr.reshape(-1)


def feature_vector(landmarks: dict) -> np.ndarray | None:
    """Monta o vetor de features. None se nenhuma mão foi detectada."""
    left = landmarks.get("left_hand")
    right = landmarks.get("right_hand")
    if not left and not right:
        return None

    vec = np.zeros(FEATURE_LENGTH, dtype=np.float32)
    if left:
        vec[0:63] = normalize_hand(left)
        vec[126] = 1.0
    if right:
        vec[63:126] = normalize_hand(right)
        vec[127] = 1.0
    return vec

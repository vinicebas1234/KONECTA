"""LSAE — augmentation espacial sobre features de landmarks.

Opera sobre a representação normalizada (punho na origem, escala
punho→MCP ≈ 1): rotação rígida, escala e jitter gaussiano por mão.
Todas as funções recebem arr (T, 128) — imagens usam T=1 — e aplicam
transformações rígidas de forma consistente ao longo dos frames.

Layout do vetor: [mão esq. 63][mão dir. 63][flag esq.][flag dir.]
"""
import numpy as np

HAND_SLICES = (slice(0, 63), slice(63, 126))
FLAG_INDICES = (126, 127)


def _rotation_matrix(rng: np.random.Generator, max_deg: float) -> np.ndarray:
    """Rotação principal no plano da imagem (z), leve fora do plano (x, y)."""
    az = np.deg2rad(rng.uniform(-max_deg, max_deg))
    ax = np.deg2rad(rng.uniform(-max_deg, max_deg) * 0.3)
    ay = np.deg2rad(rng.uniform(-max_deg, max_deg) * 0.3)
    cz, sz = np.cos(az), np.sin(az)
    cx, sx = np.cos(ax), np.sin(ax)
    cy, sy = np.cos(ay), np.sin(ay)
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    return rz @ ry @ rx


def _apply_per_hand(arr: np.ndarray, transform) -> np.ndarray:
    """Aplica transform((T, 21, 3)) -> (T, 21, 3) a cada mão presente."""
    out = arr.copy()
    for sl, flag in zip(HAND_SLICES, FLAG_INDICES):
        present = out[:, flag] > 0.5
        if not present.any():
            continue
        points = out[:, sl].reshape(len(out), 21, 3)
        points[present] = transform(points[present])
        out[:, sl] = points.reshape(len(out), -1)
    return out


def rotate(arr: np.ndarray, rng: np.random.Generator,
           intensity: float) -> np.ndarray:
    """Rotação rígida (uma por mão, constante ao longo da sequência)."""
    def transform(points):
        rot = _rotation_matrix(rng, 25.0 * intensity)
        return points @ rot.T
    return _apply_per_hand(arr, transform)


def scale(arr: np.ndarray, rng: np.random.Generator,
          intensity: float) -> np.ndarray:
    """Variação de escala/proporção da mão."""
    def transform(points):
        factor = 1.0 + rng.uniform(-0.2, 0.2) * intensity
        return points * factor
    return _apply_per_hand(arr, transform)


def jitter(arr: np.ndarray, rng: np.random.Generator,
           intensity: float) -> np.ndarray:
    """Ruído gaussiano controlado por coordenada (por frame)."""
    sigma = 0.05 * intensity
    def transform(points):
        return points + rng.normal(0.0, sigma, points.shape)
    return _apply_per_hand(arr, transform)

"""LSAE — augmentation temporal sobre sequências de landmarks.

Gera variações plausíveis de ritmo e cadência do sinal:
time warp (velocidade variável suave) e frame stutter (repetição
de frames, simulando travadas de câmera/execução).

Sequências: arr (T, 128). As flags de presença são re-binarizadas
após interpolação.
"""
import numpy as np

FLAG_COLUMNS = slice(126, 128)


def time_warp(arr: np.ndarray, rng: np.random.Generator,
              intensity: float) -> np.ndarray:
    """Reamostra a sequência com uma curva de velocidade suave e aleatória."""
    n_frames = len(arr)
    if n_frames < 4:
        return arr.copy()

    n_knots = 4
    speeds = rng.uniform(1.0 - 0.6 * intensity, 1.0 + 0.6 * intensity, n_knots)
    speed = np.interp(np.linspace(0, n_knots - 1, n_frames),
                      np.arange(n_knots), speeds)
    positions = np.cumsum(speed)
    positions = (positions - positions[0]) / (positions[-1] - positions[0])
    positions *= (n_frames - 1)

    lower = np.floor(positions).astype(int)
    upper = np.minimum(lower + 1, n_frames - 1)
    frac = (positions - lower)[:, None]
    out = arr[lower] * (1.0 - frac) + arr[upper] * frac
    out[:, FLAG_COLUMNS] = (out[:, FLAG_COLUMNS] > 0.5).astype(arr.dtype)
    return out


def frame_stutter(arr: np.ndarray, rng: np.random.Generator,
                  intensity: float) -> np.ndarray:
    """Repete o frame anterior em pontos aleatórios (variação de frames)."""
    out = arr.copy()
    prob = 0.12 * intensity
    for t in range(1, len(out)):
        if rng.random() < prob:
            out[t] = out[t - 1]
    return out

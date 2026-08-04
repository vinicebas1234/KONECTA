"""LSAE — pipeline de augmentation.

REGRA OBRIGATÓRIA (anti data-leakage, seção 35 da especificação):
o LSAE é aplicado somente ao conjunto de TREINO, depois do split.
Validação e teste permanecem originais. Os trainers garantem isso
chamando o augmenter apenas sobre (X_train, y_train).

Modo automático: intensidade média e fator escolhido para levar a
menor classe a ~30 exemplos de treino (limitado a 5x).
"""
from dataclasses import asdict, dataclass

import numpy as np

from . import spatial, temporal

AUTO_TARGET_PER_CLASS = 30
MAX_FACTOR = 5


@dataclass
class LsaeConfig:
    enabled: bool = False
    auto: bool = True
    intensity: float = 0.5     # 0..1
    factor: int = 3            # dataset final ≈ original × factor
    spatial: bool = True       # rotação
    scale: bool = True
    noise: bool = True
    temporal: bool = True      # só tem efeito em sequências

    def to_dict(self) -> dict:
        return asdict(self)


def resolve(config: LsaeConfig, y_train: np.ndarray) -> LsaeConfig:
    """Aplica o modo automático sobre a distribuição real do treino."""
    if not config.auto:
        return config
    _, counts = np.unique(y_train, return_counts=True)
    smallest = int(counts.min()) if len(counts) else 1
    factor = int(np.ceil(AUTO_TARGET_PER_CLASS / max(smallest, 1)))
    return LsaeConfig(enabled=config.enabled, auto=True, intensity=0.5,
                      factor=int(np.clip(factor, 2, MAX_FACTOR)),
                      spatial=True, scale=True, noise=True, temporal=True)


def _augment_one(arr: np.ndarray, config: LsaeConfig,
                 rng: np.random.Generator, is_sequence: bool) -> np.ndarray:
    out = arr
    if config.spatial:
        out = spatial.rotate(out, rng, config.intensity)
    if config.scale:
        out = spatial.scale(out, rng, config.intensity)
    if config.temporal and is_sequence:
        out = temporal.time_warp(out, rng, config.intensity)
        out = temporal.frame_stutter(out, rng, config.intensity)
    if config.noise:
        out = spatial.jitter(out, rng, config.intensity)
    return out.astype(arr.dtype)


def augment_train_set(X: np.ndarray, y: np.ndarray, config: LsaeConfig,
                      seed: int = 42) -> tuple[np.ndarray, np.ndarray, LsaeConfig]:
    """Expande (X, y) de TREINO com variações sintéticas.

    X: (N, F) para imagens ou (N, T, F) para sequências.
    Retorna (X original + sintético, y correspondente, config resolvida).
    """
    config = resolve(config, y)
    if not config.enabled or config.factor < 2:
        return X, y, config

    rng = np.random.default_rng(seed)
    is_sequence = X.ndim == 3
    synthetic_X, synthetic_y = [], []
    for i in range(len(X)):
        arr = X[i] if is_sequence else X[i][None, :]
        for _ in range(config.factor - 1):
            aug = _augment_one(arr, config, rng, is_sequence)
            synthetic_X.append(aug if is_sequence else aug[0])
            synthetic_y.append(y[i])

    X_out = np.concatenate([X, np.stack(synthetic_X)])
    y_out = np.concatenate([y, np.array(synthetic_y)])
    order = rng.permutation(len(y_out))
    return X_out[order], y_out[order], config

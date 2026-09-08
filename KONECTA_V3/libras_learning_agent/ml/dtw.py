"""Distância DTW (Dynamic Time Warping) entre duas sequências de landmarks.

Implementação própria — programação dinâmica O(T1×T2), sem dependência nova.
Medido neste ciclo (vídeos reais, até ~400 frames a 60fps): uma matriz 400×400
roda em ~0.15s com a matriz de custo vetorizada via numpy e o preenchimento da
DP sobre listas Python (mais rápido que indexar `ndarray` elemento a elemento
num laço). Para o volume deste ciclo (dezenas de sinais, milhares de pares no
pior caso) isso fica na casa de minutos, não horas — não compensa trocar por
scipy/dtaidistance para tão pouco.
"""

from __future__ import annotations

import numpy as np


def dtw_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Distância DTW entre `a` (T1, D) e `b` (T2, D), custo local = euclidiana por frame.

    Normalizada pelo comprimento do caminho (T1+T2): sem isso, sequências mais
    curtas teriam vantagem artificial no kNN por acumularem menos custo total.
    """
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return float("inf")

    diff = a[:, None, :] - b[None, :, :]
    cost = np.sqrt((diff * diff).sum(axis=2)).tolist()  # (n, m); lista é mais rápida no laço abaixo

    dtw = [[float("inf")] * (m + 1) for _ in range(n + 1)]
    dtw[0][0] = 0.0
    for i in range(1, n + 1):
        row, prev_row, cost_row = dtw[i], dtw[i - 1], cost[i - 1]
        for j in range(1, m + 1):
            row[j] = cost_row[j - 1] + min(prev_row[j], row[j - 1], prev_row[j - 1])

    return dtw[n][m] / (n + m)

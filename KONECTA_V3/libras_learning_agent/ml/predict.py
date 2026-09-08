"""Inferência: kNN por distância DTW sobre um conjunto de referências.

Função pura — não toca banco, não decide status/promoção de modelo. Quem
chama (API, script de avaliação, ciclo futuro) decide o que fazer com o
ranking devolvido.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

import numpy as np

from libras_learning_agent.ml.dataset import Sample
from libras_learning_agent.ml.dtw import dtw_distance


def predict(references: Sequence[Sample], query_sequence: np.ndarray, k: int = 5) -> List[Tuple[str, float]]:
    """Os `k` sinais mais próximos de `query_sequence` por DTW, ordenados por distância.

    kNN sobre as amostras cruas (cada referência é sua própria amostra, não
    uma média por sinal — é o modo que o projeto já mediu como o melhor, ver
    `KONECTA_V3/RECONHECIMENTO_RECOMENDACAO.md` seção 5.1). Sem repetir sinal:
    se duas referências do mesmo sinal aparecerem entre as mais próximas, só a
    de menor distância conta para o ranking.
    """
    scored = sorted(
        ((dtw_distance(query_sequence, ref.sequence), ref.sign) for ref in references),
        key=lambda pair: pair[0],
    )
    ranking: List[Tuple[str, float]] = []
    seen = set()
    for distance, sign in scored:
        if sign in seen:
            continue
        seen.add(sign)
        ranking.append((sign, distance))
        if len(ranking) >= k:
            break
    return ranking

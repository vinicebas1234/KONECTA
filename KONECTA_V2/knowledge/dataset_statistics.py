"""Estatisticas gerais do dataset: contagens, distribuicao e balanceamento."""

from __future__ import annotations

import math
from collections import Counter
from typing import Optional

from core.types import Amostra, EstatisticasDataset


def _media(valores: list[Optional[float]]) -> Optional[float]:
    presentes = [v for v in valores if v is not None]
    return sum(presentes) / len(presentes) if presentes else None


class DatasetStatistics:
    """Calcula as estatisticas descritivas de um conjunto de amostras."""

    def calcular(self, amostras: list[Amostra]) -> EstatisticasDataset:
        por_sinal = Counter(a.sinal for a in amostras)
        por_sinalizante = Counter(a.sinalizante for a in amostras)

        return EstatisticasDataset(
            n_amostras=len(amostras),
            n_sinais=len(por_sinal),
            n_sinalizantes=len(por_sinalizante),
            amostras_por_sinal=dict(por_sinal),
            amostras_por_sinalizante=dict(por_sinalizante),
            balanceamento=self._balanceamento(por_sinal),
            duracao_media_s=_media([a.duracao_s for a in amostras]),
            fps_medio=_media([a.fps for a in amostras]),
            confianca_media=_media([a.confianca_media for a in amostras]),
            taxa_landmarks_perdidos=_media(
                [a.taxa_landmarks_perdidos for a in amostras]
            ),
        )

    @staticmethod
    def _balanceamento(por_sinal: Counter) -> float:
        """Entropia normalizada da distribuicao entre classes.

        1.0 significa todas as classes com o mesmo numero de amostras;
        valores proximos de 0 indicam forte desbalanceamento.
        """
        if len(por_sinal) <= 1:
            return 1.0
        total = sum(por_sinal.values())
        entropia = -sum(
            (n / total) * math.log(n / total) for n in por_sinal.values() if n > 0
        )
        return entropia / math.log(len(por_sinal))

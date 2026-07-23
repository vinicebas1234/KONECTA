"""Módulo LSAE Engine — Etapa 10 do KONECTA V2.

Reconhecimento de sinais em tempo real usando modelos treinados
pela Etapa 9 (AI Engine).
"""

from lsae.reconhecedor import ReconhecedorSinais
from lsae.types import (
    ModoRecognition,
    PredictedSinal,
    ResultadoRecognition,
)

__all__ = [
    "ModoRecognition",
    "PredictedSinal",
    "ResultadoRecognition",
    "ReconhecedorSinais",
]

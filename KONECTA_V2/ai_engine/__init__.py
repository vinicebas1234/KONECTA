"""Módulo AI Engine — Etapa 9 do KONECTA V2.

Responsável por treinamento e avaliação de modelos para reconhecimento
de sinais de Libras. Exporta métricas para o AI Research Assistant.
"""

from ai_engine.treinador import TreinadorModelo
from ai_engine.types import (
    AnaliseErros,
    MatrizConfusao,
    MetricasDesempenho,
    ResultadoTreinamento,
    TipoModelo,
)

__all__ = [
    "TipoModelo",
    "MetricasDesempenho",
    "ResultadoTreinamento",
    "MatrizConfusao",
    "AnaliseErros",
    "TreinadorModelo",
]

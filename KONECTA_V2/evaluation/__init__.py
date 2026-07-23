"""Módulo de Avaliação — Etapa 11 do KONECTA V2.

Análise completa de modelos com foco em desempenho cross-signer
e generalização entre diferentes sinalizantes.
"""

from evaluation.avaliador import AvaliadorModelo
from evaluation.types import (
    MatrizConfusaoDetalhada,
    MetricasCrossSigners,
    RelatorioAvaliacao,
)

__all__ = [
    "MetricasCrossSigners",
    "MatrizConfusaoDetalhada",
    "RelatorioAvaliacao",
    "AvaliadorModelo",
]

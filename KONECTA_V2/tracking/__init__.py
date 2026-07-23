"""Módulo Tracking Engine — Etapa 6 do KONECTA V2.

Responsável por analisar trajetórias de pontos de articulação,
determinar dominância de mão e caracterar o movimento de sinais.
"""

from tracking.analisador import AnalisadorTrajetoria
from tracking.types import (
    AnaliseMao,
    AnaliseTrajetoria,
    Dominancia,
    LocalTrajetoria,
    LayoutSinalizacao,
    PontoReferencia,
    TrajetoData,
)

__all__ = [
    "Dominancia",
    "LocalTrajetoria",
    "PontoReferencia",
    "LayoutSinalizacao",
    "TrajetoData",
    "AnaliseMao",
    "AnaliseTrajetoria",
    "AnalisadorTrajetoria",
]

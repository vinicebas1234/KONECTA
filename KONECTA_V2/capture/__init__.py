"""Módulo de captura — Etapa 4 do KONECTA V2.

Responsável por capturar vídeos de webcam ou arquivo e extrair frames
para análise posterior pelo Knowledge Engine.
"""

from capture.capturer import CaptorVideo
from capture.types import ConfigCaptura, FrameCapturado, SessaoCaptura
from capture.validador import ResultadoValidacao, ValidadorCaptura

__all__ = [
    "ConfigCaptura",
    "FrameCapturado",
    "SessaoCaptura",
    "CaptorVideo",
    "ValidadorCaptura",
    "ResultadoValidacao",
]

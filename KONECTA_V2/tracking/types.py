"""Tipos do Tracking Engine — Análise de trajetória e layout de pontos."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Dominancia(str, Enum):
    """Dominância da mão no sinal."""

    DIREITA = "direita"
    ESQUERDA = "esquerda"
    AMBAS = "ambas"
    INDEFINIDA = "indefinida"


class LocalTrajetoria(str, Enum):
    """Localização do gesto no espaço de sinalização."""

    NEUTRO = "neutro"  # Frente ao corpo
    ALTO = "alto"  # Acima dos ombros
    BAIXO = "baixo"  # Abaixo da cintura
    LATERAL = "lateral"  # Fora do corpo
    FRONTAL = "frontal"  # Próximo ao rosto


@dataclass
class PontoReferencia:
    """Ponto de referência para normalização (ex: ombro, cotovelo)."""

    nome: str
    indice_mediapipe: int  # Índice no vetor de landmarks
    descricao: str = ""


@dataclass
class LayoutSinalizacao:
    """Layout de pontos críticos para um sinal (quais landmarks importam)."""

    nome: str
    pontos_criticos: list[str]  # Nomes dos pontos críticos
    exclui_repouso: bool = False  # Excluir frames de repouso
    minimo_frames_movimento: int = 5  # Mínimo de frames com movimento detectado
    confianca_minima: float = 0.3  # Confiança mínima de detecção

    @property
    def n_pontos_criticos(self) -> int:
        """Número de pontos críticos."""
        return len(self.pontos_criticos)


@dataclass
class TrajetoData:
    """Trajetória de um único ponto ao longo de frames."""

    nome_ponto: str
    xs: list[float]  # Coordenadas X de cada frame
    ys: list[float]  # Coordenadas Y de cada frame
    zs: list[float]  # Profundidade (Z)
    confiancas: list[float]  # Confiança de cada frame

    @property
    def n_frames(self) -> int:
        """Número de frames na trajetória."""
        return len(self.xs)

    @property
    def comprimento_pixel(self) -> float:
        """Comprimento total da trajetória em pixels."""
        import math

        total = 0.0
        for i in range(1, self.n_frames):
            dx = self.xs[i] - self.xs[i - 1]
            dy = self.ys[i] - self.ys[i - 1]
            total += math.sqrt(dx * dx + dy * dy)
        return total

    @property
    def confianca_media(self) -> float:
        """Confiança média da trajetória."""
        import numpy as np

        return float(np.mean(self.confiancas)) if self.confiancas else 0.0


@dataclass
class AnaliseMao:
    """Análise de uma mão em um sinal."""

    lado: str  # "direita" ou "esquerda"
    dominancia_estimada: Dominancia
    ativa_em_frames: int  # Frames onde a mão foi detectada com confiança
    velocidade_media: float  # Pixels/frame médio
    amplitude_total: float  # Distância total percorrida
    estabilidade: float  # Quão consistente é o movimento (0-1)
    trajetorias: dict[str, TrajetoData]  # Trajetórias dos dedos principais


@dataclass
class AnaliseTrajetoria:
    """Análise completa de trajetória de um sinal."""

    id_sessao: str
    dominancia: Dominancia
    local_principal: LocalTrajetoria
    maos: dict[str, AnaliseMao]  # "direita" e/ou "esquerda"
    duracao_movimento_frames: int
    velocidade_media_geral: float
    complexidade_estimada: float  # 0=simples, 1=complexo

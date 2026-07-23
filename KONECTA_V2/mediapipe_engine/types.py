"""Tipos do MediaPipe Engine — Extração de landmarks."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Ponto3D:
    """Um ponto 3D com confiança."""

    x: float
    y: float
    z: float
    confianca: float = 1.0

    def normalizar(self, largura: int, altura: int) -> None:
        """Normaliza coordenadas para [0, 1]."""
        if largura > 0:
            self.x /= largura
        if altura > 0:
            self.y /= altura

    def desnormalizar(self, largura: int, altura: int) -> None:
        """Desnormaliza coordenadas de [0, 1] para pixel."""
        self.x *= largura
        self.y *= altura


@dataclass
class LandmarksFrame:
    """Landmarks extraídos de um frame único."""

    numero_frame: int
    timestamp_ms: float
    mao_direita: list[Ponto3D] = field(default_factory=list)
    mao_esquerda: list[Ponto3D] = field(default_factory=list)
    corpo: list[Ponto3D] = field(default_factory=list)
    confianca_media: float = 0.0

    @property
    def n_pontos_detectados(self) -> int:
        """Número total de pontos detectados (todos os canais)."""
        return len(self.mao_direita) + len(self.mao_esquerda) + len(self.corpo)

    @property
    def pontos_faltantes(self) -> int:
        """Número de pontos que deveriam estar presentes mas não estão."""
        esperado = 21 + 21 + 33  # Mão direita + esquerda + corpo
        return esperado - self.n_pontos_detectados


@dataclass
class ExtratorLandmarks:
    """Configuração de extração de landmarks."""

    modelo: str = "hand"  # "hand", "pose", "holistic"
    static_image_mode: bool = False
    max_num_hands: int = 2
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5

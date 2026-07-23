"""Tipos compartilhados do módulo de captura."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ConfigCaptura:
    """Configuração de captura de vídeo."""

    fps: int = 30
    resolucao: tuple[int, int] = (640, 480)
    codec: str = "mp4v"
    duracao_max_segundos: int = 30
    verificar_luz: bool = True
    luz_minima_pct: float = 0.1


@dataclass
class FrameCapturado:
    """Um frame capturado do vídeo."""

    numero: int
    timestamp_ms: float
    dados: bytes
    qualidade_luz: float = 0.0
    deteccoes_mediapipe: Optional[dict] = None

    @property
    def rejeitar_por_luz(self) -> bool:
        """Verifica se o frame deve ser rejeitado por falta de luz."""
        return self.qualidade_luz < 0.1


@dataclass
class SessaoCaptura:
    """Metadados de uma sessão de captura."""

    id: str
    sinal: str
    sinalizante: str
    timestamp_inicio: float
    caminho_video: Optional[Path] = None
    frames: list[FrameCapturado] = field(default_factory=list)
    duracao_segundos: float = 0.0
    fps_realizado: float = 0.0
    qualidade_media_luz: float = 0.0
    observacoes: str = ""

    def adicionar_frame(self, frame: FrameCapturado) -> None:
        """Adiciona um frame à sessão."""
        self.frames.append(frame)

    @property
    def n_frames(self) -> int:
        """Número de frames capturados."""
        return len(self.frames)

    @property
    def frames_rejeitados_luz(self) -> int:
        """Número de frames rejeitados por falta de luz."""
        return sum(1 for f in self.frames if f.rejeitar_por_luz)

"""Tipos do LSAE Engine — Reconhecimento de sinais."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ModoRecognition(str, Enum):
    """Modo de reconhecimento."""

    TEMPO_REAL = "tempo_real"  # Streaming de vídeo
    VIDEO_COMPLETO = "video_completo"  # Arquivo
    FRAME_UNICO = "frame_unico"  # Single frame


@dataclass
class PredictedSinal:
    """Predição de um sinal."""

    sinal: str
    confianca: float  # 0-1
    ranking: list[tuple[str, float]]  # [(sinal, prob), ...]
    timestamp_ms: float = 0.0
    frame_numero: int = 0

    @property
    def eh_confiavel(self) -> bool:
        """Verifica se a predição é confiável (>70%)."""
        return self.confianca > 0.7

    @property
    def diferenca_top_2(self) -> float:
        """Diferença entre 1º e 2º lugar."""
        if len(self.ranking) >= 2:
            return self.ranking[0][1] - self.ranking[1][1]
        return 1.0


@dataclass
class ResultadoRecognition:
    """Resultado de reconhecimento de uma sessão."""

    id_sessao: str
    modo: ModoRecognition
    predicoes: list[PredictedSinal]
    taxa_confianca_media: float
    sinal_dominante: str
    tempo_processamento_s: float
    n_frames_processados: int

    @property
    def acertos_confiaveis(self) -> int:
        """Número de predições confiáveis."""
        return sum(1 for p in self.predicoes if p.eh_confiavel)

    @property
    def taxa_confianca_geral(self) -> float:
        """Taxa de predições com confiança > 70%."""
        if not self.predicoes:
            return 0.0
        return self.acertos_confiaveis / len(self.predicoes)

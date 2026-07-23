"""Enriquecimento de amostras com análise de tracking.

Toma amostras com landmarks já carregados e executa análise de trajetória
para preencher campos de tracking (dominância, complexidade, velocidade).
"""

from __future__ import annotations

import numpy as np

from core.types import Amostra, Dominancia
from mediapipe_engine.types import LandmarksFrame, Ponto3D
from tracking import AnalisadorTrajetoria


class AmostralEnricher:
    """Enriquece amostras com dados de análise de trajetória."""

    def enriquecer(self, amostra: Amostra) -> Amostra:
        """Enriquece uma amostra usando seus landmarks."""
        if amostra.landmarks is None or amostra.landmarks.shape[0] == 0:
            # Sem landmarks, não há nada a enriquecer
            return amostra

        # Converter tensor de landmarks em LandmarksFrame
        landmarks_frames = self._tensor_para_frames(amostra.landmarks)

        # Analisar trajetórias
        analisador = AnalisadorTrajetoria()
        analise = analisador.analisar_landmarks(
            id_sessao=amostra.id,
            landmarks_maos=landmarks_frames,
        )

        # Enriquecer amostra
        amostra.dominancia = analise.dominancia
        amostra.velocidade_media = analise.velocidade_media_geral
        amostra.complexidade = analise.complexidade_estimada

        return amostra

    def enriquecer_lote(self, amostras: list[Amostra]) -> list[Amostra]:
        """Enriquece um lote de amostras."""
        return [self.enriquecer(a) for a in amostras]

    @staticmethod
    def _tensor_para_frames(landmarks: np.ndarray) -> list[LandmarksFrame]:
        """Converte tensor (frames, 21, 3) em lista de LandmarksFrame."""
        frames = []

        for frame_idx in range(landmarks.shape[0]):
            frame_data = landmarks[frame_idx]  # (21, 3)

            # Criar Ponto3D para cada dos 21 pontos
            pontos = []
            for ponto_idx in range(frame_data.shape[0]):
                x, y, z = frame_data[ponto_idx]
                ponto = Ponto3D(x=x, y=y, z=z, confianca=1.0)
                pontos.append(ponto)

            # Criar LandmarksFrame
            lm_frame = LandmarksFrame(
                numero_frame=frame_idx,
                timestamp_ms=frame_idx * 33.33,  # ~30 fps
                mao_direita=pontos,  # Assumir mão direita
                mao_esquerda=[],
                corpo=[],
            )
            frames.append(lm_frame)

        return frames


# Singleton global
_enricher = AmostralEnricher()


def enriquecer_amostra(amostra: Amostra) -> Amostra:
    """Interface pública: enriquece uma amostra."""
    return _enricher.enriquecer(amostra)


def enriquecer_lote(amostras: list[Amostra]) -> list[Amostra]:
    """Interface pública: enriquece um lote."""
    return _enricher.enriquecer_lote(amostras)

"""Serviço de pipeline end-to-end: Captura → Landmarks → Tracking → Análise."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

import numpy as np

from backend.services.capture_service import (
    _capture_service as capture_service,
)
from core.types import Amostra
from mediapipe_engine import ExtratormediaPipeHands, ExtratormediaPipePose
from tracking import AnalisadorTrajetoria, AnaliseTrajetoria


class PipelineService:
    """Orquestra captura → landmarks → tracking → conhecimento."""

    def __init__(self):
        self._lock = threading.Lock()
        self._analises_cache: dict[str, AnaliseTrajetoria] = {}

    def processar_sessao_completa(
        self,
        id_sessao: str,
        sinal: str,
        sinalizante: str,
    ) -> dict:
        """Processa uma sessão completa e retorna análise + amostra."""
        with self._lock:
            # Recuperar sessão de captura
            sessao = capture_service.obter_sessao(id_sessao)
            if not sessao:
                raise ValueError(f"Sessão '{id_sessao}' não encontrada")

            if sessao.n_frames == 0:
                raise ValueError(
                    f"Sessão '{id_sessao}' não contém frames capturados"
                )

            # Etapa 5: Extrair landmarks
            extrator_maos = ExtratormediaPipeHands()
            landmarks_maos = extrator_maos.extrair_da_sessao(sessao)
            extrator_maos.limpar()

            extrator_corpo = ExtratormediaPipePose()
            landmarks_corpo = extrator_corpo.extrair_da_sessao(sessao)
            extrator_corpo.limpar()

            # Etapa 6: Analisar trajetórias
            analisador = AnalisadorTrajetoria()
            analise_trajetoria = analisador.analisar_landmarks(
                id_sessao=id_sessao,
                landmarks_maos=landmarks_maos,
                landmarks_corpo=landmarks_corpo,
            )
            self._analises_cache[id_sessao] = analise_trajetoria

            # Converter para Amostra (Core type)
            amostra = self._criar_amostra_de_sessao(
                sessao,
                sinal,
                sinalizante,
                landmarks_maos,
                analise_trajetoria,
            )

            return {
                "id": amostra.id,
                "sinal": amostra.sinal,
                "sinalizante": amostra.sinalizante,
                "n_frames": amostra.n_frames,
                "duracao_s": amostra.duracao_s,
                "landmarks_shape": (
                    amostra.landmarks.shape if amostra.landmarks is not None else None
                ),
                "trajetoria": {
                    "dominancia": analise_trajetoria.dominancia.value,
                    "local_principal": analise_trajetoria.local_principal.value,
                    "complexidade": analise_trajetoria.complexidade_estimada,
                    "velocidade_media": analise_trajetoria.velocidade_media_geral,
                },
            }

    def _criar_amostra_de_sessao(
        self,
        sessao,
        sinal: str,
        sinalizante: str,
        landmarks_maos: list,
        analise_trajetoria: AnaliseTrajetoria,
    ) -> Amostra:
        """Converte sessão de captura em Amostra (Core type)."""
        # Montar tensor de landmarks: (frames, 21 pontos mão, 3 coords)
        landmarks_array = None
        if landmarks_maos and len(landmarks_maos) > 0:
            n_frames = len(landmarks_maos)
            n_pontos = 21  # MediaPipe Hand
            landmarks_array = np.zeros((n_frames, n_pontos, 3))

            for frame_idx, lm_frame in enumerate(landmarks_maos):
                # Preencher mão direita (pontos 0-20)
                if lm_frame.mao_direita:
                    for ponto_idx, ponto in enumerate(
                        lm_frame.mao_direita[:n_pontos]
                    ):
                        landmarks_array[frame_idx, ponto_idx, 0] = ponto.x
                        landmarks_array[frame_idx, ponto_idx, 1] = ponto.y
                        landmarks_array[frame_idx, ponto_idx, 2] = ponto.z

        # Criar amostra
        amostra = Amostra(
            id=sessao.id,
            sinal=sinal,
            sinalizante=sinalizante,
            n_frames=sessao.n_frames,
            duracao_s=sessao.duracao_segundos,
            fps=sessao.fps_realizado,
            landmarks=landmarks_array,
            qualidade_luz_media=sessao.qualidade_media_luz,
            confianca_media=np.mean(
                [lm.confianca_media for lm in landmarks_maos]
            ) if landmarks_maos else 0.0,
        )

        return amostra

    def obter_analise_trajetoria(
        self,
        id_sessao: str,
    ) -> Optional[AnaliseTrajetoria]:
        """Recupera análise de trajetória cacheada."""
        return self._analises_cache.get(id_sessao)


# Singleton global
_pipeline_service = PipelineService()


def processar_sessao_completa(
    id_sessao: str,
    sinal: str,
    sinalizante: str,
) -> dict:
    """Interface pública: processa sessão completa."""
    return _pipeline_service.processar_sessao_completa(id_sessao, sinal, sinalizante)


def obter_analise_trajetoria(id_sessao: str) -> Optional[dict]:
    """Interface pública: recupera análise."""
    analise = _pipeline_service.obter_analise_trajetoria(id_sessao)
    if not analise:
        return None

    return {
        "id_sessao": analise.id_sessao,
        "dominancia": analise.dominancia.value,
        "local_principal": analise.local_principal.value,
        "complexidade": analise.complexidade_estimada,
        "velocidade_media": analise.velocidade_media_geral,
        "maos": {
            lado: {
                "ativa_em_frames": mao.ativa_em_frames,
                "velocidade_media": mao.velocidade_media,
                "amplitude_total": mao.amplitude_total,
                "estabilidade": mao.estabilidade,
            }
            for lado, mao in analise.maos.items()
        },
    }

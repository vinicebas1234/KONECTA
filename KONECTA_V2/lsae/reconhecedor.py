"""Reconhecedor de sinais em tempo real."""

from __future__ import annotations

import time
from typing import Optional

import numpy as np

from ai_engine import TreinadorModelo
from core.types import Amostra
from lsae.types import ModoRecognition, PredictedSinal, ResultadoRecognition
from mediapipe_engine.types import LandmarksFrame


class ReconhecedorSinais:
    """Realiza reconhecimento de sinais usando modelo treinado."""

    def __init__(self, treinador: TreinadorModelo):
        """Inicializa reconhecedor com modelo já treinado."""
        if treinador.modelo is None:
            raise ValueError("Modelo não foi treinado")

        self.treinador = treinador
        self.modelo = treinador.modelo
        self.scaler = treinador.scaler
        self.classes = treinador.classes

    def reconhecer_sessao(
        self,
        id_sessao: str,
        landmarks_lista: list[LandmarksFrame],
        modo: ModoRecognition = ModoRecognition.VIDEO_COMPLETO,
    ) -> ResultadoRecognition:
        """Reconhece sinais em uma sessão."""
        tempo_inicio = time.time()

        # Converter landmarks em amostras unitárias
        predicoes = []

        for frame_idx, lm_frame in enumerate(landmarks_lista):
            # Pular frames sem landmarks
            if not lm_frame.mao_direita or len(lm_frame.mao_direita) == 0:
                continue

            # Extrair features do frame
            features = self._extrair_features_frame(lm_frame)

            # Normalizar
            features_norm = self.scaler.transform([features])[0]

            # Prever
            predicao_classe = self.modelo.predict([features_norm])[0]
            probabilidades = self.modelo.predict_proba([features_norm])[0]

            # Ordenar por confiança
            indices_ordenados = np.argsort(-probabilidades)
            ranking = [
                (self.classes[idx], float(probabilidades[idx]))
                for idx in indices_ordenados
            ]

            sinal_predito = PredictedSinal(
                sinal=self.classes[predicao_classe],
                confianca=float(probabilidades[predicao_classe]),
                ranking=ranking,
                timestamp_ms=lm_frame.timestamp_ms,
                frame_numero=frame_idx,
            )
            predicoes.append(sinal_predito)

        tempo_processamento = time.time() - tempo_inicio

        # Sinal dominante (mais frequente)
        if predicoes:
            sinais_preditos = [p.sinal for p in predicoes]
            sinal_dominante = max(set(sinais_preditos), key=sinais_preditos.count)
            taxa_confianca_media = np.mean([p.confianca for p in predicoes])
        else:
            sinal_dominante = "DESCONHECIDO"
            taxa_confianca_media = 0.0

        return ResultadoRecognition(
            id_sessao=id_sessao,
            modo=modo,
            predicoes=predicoes,
            taxa_confianca_media=taxa_confianca_media,
            sinal_dominante=sinal_dominante,
            tempo_processamento_s=tempo_processamento,
            n_frames_processados=len(predicoes),
        )

    def reconhecer_landmarks(
        self,
        landmarks: np.ndarray,
    ) -> PredictedSinal:
        """Reconhece um tensor de landmarks única."""
        if landmarks.shape != (30, 21, 3):
            raise ValueError(f"Esperado shape (30, 21, 3), recebido {landmarks.shape}")

        # Extrair features (mesmo que no treinamento)
        features = self._extrair_features_tensor(landmarks)
        features_norm = self.scaler.transform([features])[0]

        # Prever
        predicao_classe = self.modelo.predict([features_norm])[0]
        probabilidades = self.modelo.predict_proba([features_norm])[0]

        # Ranking
        indices_ordenados = np.argsort(-probabilidades)
        ranking = [
            (self.classes[idx], float(probabilidades[idx]))
            for idx in indices_ordenados
        ]

        return PredictedSinal(
            sinal=self.classes[predicao_classe],
            confianca=float(probabilidades[predicao_classe]),
            ranking=ranking,
        )

    def _extrair_features_frame(self, lm_frame: LandmarksFrame) -> np.ndarray:
        """Extrai features de um frame."""
        # Montar tensor com 30 frames (repetir o frame para manter shape consistente)
        tensor = np.zeros((30, 21, 3))

        if lm_frame.mao_direita:
            for i, ponto in enumerate(lm_frame.mao_direita[:21]):
                # Preencher todos os 30 frames com o mesmo ponto
                for f in range(30):
                    tensor[f, i, 0] = ponto.x
                    tensor[f, i, 1] = ponto.y
                    tensor[f, i, 2] = ponto.z

        return self._extrair_features_tensor(tensor)

    @staticmethod
    def _extrair_features_tensor(landmarks: np.ndarray) -> np.ndarray:
        """Extrai features de um tensor de landmarks (mesmo que no treinamento)."""
        features = []

        # Flatten
        features.extend(landmarks.flatten())

        # Estatísticas de velocidade
        if landmarks.shape[0] > 1:
            velocidades = np.sqrt(np.sum(np.diff(landmarks, axis=0) ** 2, axis=-1))
            features.extend([
                np.mean(velocidades),
                np.std(velocidades) if np.std(velocidades) > 0 else 0,
                np.max(velocidades),
                np.min(velocidades),
            ])
        else:
            features.extend([0, 0, 0, 0])

        # Amplitude
        amplitude = np.max(landmarks) - np.min(landmarks)
        features.append(amplitude)

        return np.array(features)

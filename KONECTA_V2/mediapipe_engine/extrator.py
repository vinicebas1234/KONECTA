"""Extração de landmarks com MediaPipe."""

from __future__ import annotations

import cv2
import numpy as np

try:
    import mediapipe as mp
except ImportError:
    # Versão nova do MediaPipe
    from mediapipe.python import mediapipe_framework as mp_framework

from capture.types import SessaoCaptura
from mediapipe_engine.types import ExtratorLandmarks, LandmarksFrame, Ponto3D


class ExtratormediaPipeHands:
    """Extrai landmarks das mãos usando MediaPipe Hands."""

    def __init__(self, config: ExtratorLandmarks | None = None):
        self.config = config or ExtratorLandmarks(modelo="hand")
        try:
            import mediapipe as mp
            self.mp_hands = mp.solutions.hands
            self.hands = self.mp_hands.Hands(
                static_image_mode=self.config.static_image_mode,
                max_num_hands=self.config.max_num_hands,
                min_detection_confidence=self.config.min_detection_confidence,
                min_tracking_confidence=self.config.min_tracking_confidence,
            )
        except (ImportError, AttributeError):
            # Fallback: simular extração
            self.hands = None

    def extrair_da_sessao(
        self,
        sessao: SessaoCaptura,
        normalizar: bool = True,
    ) -> list[LandmarksFrame]:
        """Extrai landmarks de todos os frames de uma sessão."""
        landmarks_lista = []

        for frame_capturado in sessao.frames:
            frame_cv = self._bytes_para_frame(frame_capturado.dados)
            altura, largura = frame_cv.shape[:2]

            landmarks = LandmarksFrame(
                numero_frame=frame_capturado.numero,
                timestamp_ms=frame_capturado.timestamp_ms,
            )

            if self.hands is not None:
                # Converter BGR para RGB
                frame_rgb = cv2.cvtColor(frame_cv, cv2.COLOR_BGR2RGB)

                # Detectar
                resultados = self.hands.process(frame_rgb)

                if resultados.multi_hand_landmarks and resultados.multi_handedness:
                    for hand_landmarks, handedness in zip(
                        resultados.multi_hand_landmarks,
                        resultados.multi_handedness,
                    ):
                        pontos = [
                            Ponto3D(
                                x=lm.x,
                                y=lm.y,
                                z=lm.z,
                                confianca=lm.z,
                            )
                            for lm in hand_landmarks.landmark
                        ]

                        if handedness.classification[0].label == "Right":
                            landmarks.mao_direita = pontos
                        else:
                            landmarks.mao_esquerda = pontos

            if normalizar:
                self._normalizar_landmarks(landmarks, largura, altura)

            # Calcular confiança média
            confiancas = [
                p.confianca
                for p in landmarks.mao_direita + landmarks.mao_esquerda
            ]
            landmarks.confianca_media = (
                np.mean(confiancas) if confiancas else 0.0
            )

            landmarks_lista.append(landmarks)

        return landmarks_lista

    def _bytes_para_frame(self, dados: bytes) -> np.ndarray:
        """Converte bytes PNG para frame OpenCV."""
        nparr = np.frombuffer(dados, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return frame

    def _normalizar_landmarks(
        self,
        landmarks: LandmarksFrame,
        largura: int,
        altura: int,
    ) -> None:
        """Normaliza landmarks para coordenadas 0-1."""
        for ponto in landmarks.mao_direita + landmarks.mao_esquerda:
            ponto.x = max(0.0, min(1.0, ponto.x))
            ponto.y = max(0.0, min(1.0, ponto.y))

    def limpar(self) -> None:
        """Libera recursos."""
        if self.hands is not None:
            self.hands.close()


class ExtratormediaPipePose:
    """Extrai landmarks do corpo usando MediaPipe Pose."""

    def __init__(self, config: ExtratorLandmarks | None = None):
        self.config = config or ExtratorLandmarks(modelo="pose")
        try:
            import mediapipe as mp
            self.mp_pose = mp.solutions.pose
            self.pose = self.mp_pose.Pose(
                static_image_mode=self.config.static_image_mode,
                min_detection_confidence=self.config.min_detection_confidence,
                min_tracking_confidence=self.config.min_tracking_confidence,
            )
        except (ImportError, AttributeError):
            # Fallback
            self.pose = None

    def extrair_da_sessao(
        self,
        sessao: SessaoCaptura,
        normalizar: bool = True,
    ) -> list[LandmarksFrame]:
        """Extrai landmarks do corpo de todos os frames."""
        landmarks_lista = []

        for frame_capturado in sessao.frames:
            frame_cv = self._bytes_para_frame(frame_capturado.dados)
            altura, largura = frame_cv.shape[:2]

            landmarks = LandmarksFrame(
                numero_frame=frame_capturado.numero,
                timestamp_ms=frame_capturado.timestamp_ms,
            )

            if self.pose is not None:
                frame_rgb = cv2.cvtColor(frame_cv, cv2.COLOR_BGR2RGB)
                resultados = self.pose.process(frame_rgb)

                if resultados.pose_landmarks:
                    pontos = [
                        Ponto3D(
                            x=lm.x,
                            y=lm.y,
                            z=lm.z,
                            confianca=lm.visibility,
                        )
                        for lm in resultados.pose_landmarks.landmark
                    ]
                    landmarks.corpo = pontos

            if normalizar:
                self._normalizar_landmarks(landmarks, largura, altura)

            confiancas = [p.confianca for p in landmarks.corpo]
            landmarks.confianca_media = (
                np.mean(confiancas) if confiancas else 0.0
            )

            landmarks_lista.append(landmarks)

        return landmarks_lista

    def _bytes_para_frame(self, dados: bytes) -> np.ndarray:
        """Converte bytes PNG para frame OpenCV."""
        nparr = np.frombuffer(dados, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return frame

    def _normalizar_landmarks(
        self,
        landmarks: LandmarksFrame,
        largura: int,
        altura: int,
    ) -> None:
        """Normaliza landmarks para coordenadas 0-1."""
        for ponto in landmarks.corpo:
            ponto.x = max(0.0, min(1.0, ponto.x))
            ponto.y = max(0.0, min(1.0, ponto.y))

    def limpar(self) -> None:
        """Libera recursos."""
        if self.pose is not None:
            self.pose.close()

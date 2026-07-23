"""Captura de vídeo e extração de frames."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from capture.types import ConfigCaptura, FrameCapturado, SessaoCaptura


class CaptorVideo:
    """Captura vídeo de webcam ou arquivo."""

    def __init__(self, config: Optional[ConfigCaptura] = None):
        self.config = config or ConfigCaptura()
        self._sessao_ativa: Optional[SessaoCaptura] = None

    def iniciar_sessao(
        self,
        sinal: str,
        sinalizante: str,
        id_sessao: Optional[str] = None,
    ) -> SessaoCaptura:
        """Inicia uma nova sessão de captura."""
        self._sessao_ativa = SessaoCaptura(
            id=id_sessao or f"{sinal}_{int(time.time())}",
            sinal=sinal,
            sinalizante=sinalizante,
            timestamp_inicio=time.time(),
        )
        return self._sessao_ativa

    def capturar_da_webcam(self, duracao_segundos: float = 5.0) -> SessaoCaptura:
        """Captura vídeo da webcam durante N segundos."""
        if not self._sessao_ativa:
            raise RuntimeError("Nenhuma sessão ativa. Chame iniciar_sessao() primeiro.")

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise RuntimeError("Não foi possível abrir a webcam.")

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.resolucao[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.resolucao[1])
        cap.set(cv2.CAP_PROP_FPS, self.config.fps)

        frames_capturados = 0
        tempo_inicio = time.time()

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                tempo_decorrido = time.time() - tempo_inicio
                if tempo_decorrido > duracao_segundos:
                    break

                qualidade_luz = self._calcular_qualidade_luz(frame)
                frame_obj = FrameCapturado(
                    numero=frames_capturados,
                    timestamp_ms=tempo_decorrido * 1000,
                    dados=self._frame_para_bytes(frame),
                    qualidade_luz=qualidade_luz,
                )

                self._sessao_ativa.adicionar_frame(frame_obj)
                frames_capturados += 1

        finally:
            cap.release()

        self._finalizar_sessao_captura(duracao_segundos)
        return self._sessao_ativa

    def capturar_do_arquivo(
        self,
        caminho_video: Path,
    ) -> SessaoCaptura:
        """Captura frames de um arquivo de vídeo."""
        if not self._sessao_ativa:
            raise RuntimeError("Nenhuma sessão ativa. Chame iniciar_sessao() primeiro.")

        if not caminho_video.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {caminho_video}")

        cap = cv2.VideoCapture(str(caminho_video))
        if not cap.isOpened():
            raise RuntimeError(f"Não foi possível abrir o vídeo: {caminho_video}")

        fps_original = cap.get(cv2.CAP_PROP_FPS)
        frames_capturados = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                qualidade_luz = self._calcular_qualidade_luz(frame)
                frame_obj = FrameCapturado(
                    numero=frames_capturados,
                    timestamp_ms=(frames_capturados / fps_original) * 1000,
                    dados=self._frame_para_bytes(frame),
                    qualidade_luz=qualidade_luz,
                )

                self._sessao_ativa.adicionar_frame(frame_obj)
                frames_capturados += 1

        finally:
            cap.release()

        self._sessao_ativa.caminho_video = caminho_video
        self._finalizar_sessao_captura(frames_capturados / fps_original)
        return self._sessao_ativa

    def _calcular_qualidade_luz(self, frame: np.ndarray) -> float:
        """Calcula um score de iluminação do frame (0 = escuro, 1 = bem iluminado)."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        v_channel = hsv[:, :, 2]
        media_brilho = np.mean(v_channel) / 255.0
        return float(media_brilho)

    def _frame_para_bytes(self, frame: np.ndarray) -> bytes:
        """Converte um frame OpenCV para bytes (PNG comprimido)."""
        _, buffer = cv2.imencode(".png", frame)
        return bytes(buffer)

    def _finalizar_sessao_captura(self, duracao_segundos: float) -> None:
        """Finaliza a sessão e calcula estatísticas."""
        if not self._sessao_ativa:
            return

        self._sessao_ativa.duracao_segundos = duracao_segundos
        self._sessao_ativa.fps_realizado = (
            self._sessao_ativa.n_frames / duracao_segundos
            if duracao_segundos > 0
            else 0
        )

        qualidades = [f.qualidade_luz for f in self._sessao_ativa.frames]
        self._sessao_ativa.qualidade_media_luz = (
            np.mean(qualidades) if qualidades else 0.0
        )

    def obter_sessao_ativa(self) -> Optional[SessaoCaptura]:
        """Retorna a sessão de captura ativa."""
        return self._sessao_ativa

    def limpar_sessao(self) -> None:
        """Limpa a sessão ativa."""
        self._sessao_ativa = None

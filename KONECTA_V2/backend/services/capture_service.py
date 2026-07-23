"""Serviço centralizado de captura de vídeo e extração de landmarks."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from capture import CaptorVideo, ConfigCaptura, ValidadorCaptura
from capture.types import SessaoCaptura
from mediapipe_engine import ExtratormediaPipeHands, ExtratormediaPipePose
from mediapipe_engine.types import LandmarksFrame


class CaptureService:
    """Gerencia sessões de captura e extração de landmarks."""

    def __init__(self):
        self._sessoes: dict[str, SessaoCaptura] = {}
        self._landmarks_maos: dict[str, list[LandmarksFrame]] = {}
        self._landmarks_corpo: dict[str, list[LandmarksFrame]] = {}
        self._lock = threading.Lock()
        self._config_padrao = ConfigCaptura(
            fps=30,
            resolucao=(640, 480),
            duracao_max_segundos=30,
        )

    def iniciar_sessao(
        self,
        id_sessao: str,
        sinal: str,
        sinalizante: str,
    ) -> SessaoCaptura:
        """Inicia uma nova sessão de captura."""
        with self._lock:
            captor = CaptorVideo(config=self._config_padrao)
            sessao = captor.iniciar_sessao(sinal, sinalizante, id_sessao)
            self._sessoes[id_sessao] = sessao
            return sessao

    def capturar_arquivo(
        self,
        id_sessao: str,
        caminho_arquivo: Path,
    ) -> SessaoCaptura:
        """Processa um arquivo de vídeo já existente."""
        with self._lock:
            if id_sessao not in self._sessoes:
                raise ValueError(f"Sessão '{id_sessao}' não encontrada")

            captor = CaptorVideo(config=self._config_padrao)
            sessao = captor.capturar_do_arquivo(caminho_arquivo)
            self._sessoes[id_sessao] = sessao
            return sessao

    def extrair_landmarks(
        self,
        id_sessao: str,
        incluir_maos: bool = True,
        incluir_corpo: bool = True,
    ) -> dict:
        """Extrai landmarks de uma sessão de captura."""
        with self._lock:
            if id_sessao not in self._sessoes:
                raise ValueError(f"Sessão '{id_sessao}' não encontrada")

            sessao = self._sessoes[id_sessao]
            resultado = {
                "id_sessao": id_sessao,
                "n_frames": sessao.n_frames,
                "landmarks_maos": None,
                "landmarks_corpo": None,
            }

            if incluir_maos and id_sessao not in self._landmarks_maos:
                extrator_maos = ExtratormediaPipeHands()
                self._landmarks_maos[id_sessao] = extrator_maos.extrair_da_sessao(
                    sessao
                )
                extrator_maos.limpar()
                resultado["landmarks_maos"] = self._serializar_landmarks(
                    self._landmarks_maos[id_sessao]
                )

            if incluir_corpo and id_sessao not in self._landmarks_corpo:
                extrator_corpo = ExtratormediaPipePose()
                self._landmarks_corpo[id_sessao] = extrator_corpo.extrair_da_sessao(
                    sessao
                )
                extrator_corpo.limpar()
                resultado["landmarks_corpo"] = self._serializar_landmarks(
                    self._landmarks_corpo[id_sessao]
                )

            return resultado

    def validar_sessao(self, id_sessao: str) -> dict:
        """Valida qualidade de uma sessão de captura."""
        with self._lock:
            if id_sessao not in self._sessoes:
                raise ValueError(f"Sessão '{id_sessao}' não encontrada")

            sessao = self._sessoes[id_sessao]
            validador = ValidadorCaptura()
            resultado_validacao = validador.validar_sessao(sessao)

            return {
                "id_sessao": id_sessao,
                "valida": resultado_validacao.valida,
                "pontuacao": resultado_validacao.pontuacao_geral,
                "problemas": resultado_validacao.problemas,
                "avisos": resultado_validacao.avisos,
            }

    def obter_sessao(self, id_sessao: str) -> Optional[SessaoCaptura]:
        """Obtém metadados de uma sessão."""
        with self._lock:
            return self._sessoes.get(id_sessao)

    def obter_metadados_sessao(self, id_sessao: str) -> dict:
        """Retorna metadados de uma sessão em formato JSON."""
        sessao = self.obter_sessao(id_sessao)
        if not sessao:
            raise ValueError(f"Sessão '{id_sessao}' não encontrada")

        return {
            "id": sessao.id,
            "sinal": sessao.sinal,
            "sinalizante": sessao.sinalizante,
            "n_frames": sessao.n_frames,
            "duracao_segundos": sessao.duracao_segundos,
            "fps_realizado": sessao.fps_realizado,
            "qualidade_media_luz": sessao.qualidade_media_luz,
            "observacoes": sessao.observacoes,
        }

    def limpar_sessao(self, id_sessao: str) -> None:
        """Limpa uma sessão e seus dados associados."""
        with self._lock:
            self._sessoes.pop(id_sessao, None)
            self._landmarks_maos.pop(id_sessao, None)
            self._landmarks_corpo.pop(id_sessao, None)

    def _serializar_landmarks(
        self, landmarks_lista: list[LandmarksFrame]
    ) -> list[dict]:
        """Converte lista de LandmarksFrame para formato JSON."""
        resultado = []
        for lm in landmarks_lista:
            frame_data = {
                "numero_frame": lm.numero_frame,
                "timestamp_ms": lm.timestamp_ms,
                "confianca_media": lm.confianca_media,
                "mao_direita": [
                    {"x": p.x, "y": p.y, "z": p.z, "confianca": p.confianca}
                    for p in lm.mao_direita
                ],
                "mao_esquerda": [
                    {"x": p.x, "y": p.y, "z": p.z, "confianca": p.confianca}
                    for p in lm.mao_esquerda
                ],
                "corpo": [
                    {"x": p.x, "y": p.y, "z": p.z, "confianca": p.confianca}
                    for p in lm.corpo
                ],
            }
            resultado.append(frame_data)
        return resultado


# Singleton global
_capture_service = CaptureService()


def iniciar_sessao(
    id_sessao: str,
    sinal: str,
    sinalizante: str,
) -> dict:
    """Interface pública: inicia uma sessão."""
    sessao = _capture_service.iniciar_sessao(id_sessao, sinal, sinalizante)
    return {
        "id": sessao.id,
        "sinal": sessao.sinal,
        "sinalizante": sessao.sinalizante,
    }


def extrair_landmarks(
    id_sessao: str,
    incluir_maos: bool = True,
    incluir_corpo: bool = True,
) -> dict:
    """Interface pública: extrai landmarks."""
    return _capture_service.extrair_landmarks(id_sessao, incluir_maos, incluir_corpo)


def validar_sessao(id_sessao: str) -> dict:
    """Interface pública: valida sessão."""
    return _capture_service.validar_sessao(id_sessao)


def obter_metadados(id_sessao: str) -> dict:
    """Interface pública: obtém metadados."""
    return _capture_service.obter_metadados_sessao(id_sessao)

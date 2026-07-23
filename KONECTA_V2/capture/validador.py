"""Validação de qualidade de captura em tempo real."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from capture.types import FrameCapturado, SessaoCaptura


@dataclass
class ResultadoValidacao:
    """Resultado da validação de uma sessão de captura."""

    valida: bool
    problemas: list[str]
    avisos: list[str]
    pontuacao_geral: float


class ValidadorCaptura:
    """Valida a qualidade de sessões de captura."""

    def __init__(
        self,
        luz_minima: float = 0.15,
        luz_maxima: float = 0.95,
        fps_minimo: float = 20.0,
        n_frames_minimo: int = 20,
    ):
        self.luz_minima = luz_minima
        self.luz_maxima = luz_maxima
        self.fps_minimo = fps_minimo
        self.n_frames_minimo = n_frames_minimo

    def validar_sessao(self, sessao: SessaoCaptura) -> ResultadoValidacao:
        """Valida uma sessão de captura completa."""
        problemas = []
        avisos = []
        pontuacoes = []

        # Validar número de frames
        if sessao.n_frames < self.n_frames_minimo:
            problemas.append(
                f"Poucos frames: {sessao.n_frames} "
                f"(mínimo: {self.n_frames_minimo})"
            )
            pontuacoes.append(0.0)
        else:
            pontuacoes.append(1.0)

        # Validar FPS
        if sessao.fps_realizado < self.fps_minimo:
            avisos.append(
                f"FPS baixo: {sessao.fps_realizado:.1f} "
                f"(esperado: {self.fps_minimo})"
            )
            pontuacoes.append(sessao.fps_realizado / self.fps_minimo)
        else:
            pontuacoes.append(1.0)

        # Validar iluminação
        problemas_luz, score_luz = self._validar_iluminacao(sessao)
        problemas.extend(problemas_luz)
        pontuacoes.append(score_luz)

        # Validar movimento (por análise de diferença entre frames)
        avisos_movimento, score_movimento = self._validar_movimento(sessao)
        avisos.extend(avisos_movimento)
        pontuacoes.append(score_movimento)

        pontuacao_geral = float(np.mean(pontuacoes)) if pontuacoes else 0.0
        valida = len(problemas) == 0 and pontuacao_geral >= 0.6

        return ResultadoValidacao(
            valida=valida,
            problemas=problemas,
            avisos=avisos,
            pontuacao_geral=pontuacao_geral,
        )

    def _validar_iluminacao(self, sessao: SessaoCaptura) -> tuple[list[str], float]:
        """Valida a iluminação média da sessão."""
        qualidades = [f.qualidade_luz for f in sessao.frames]
        if not qualidades:
            return ["Nenhum frame capturado"], 0.0

        media = np.mean(qualidades)
        problemas = []

        if media < self.luz_minima:
            problemas.append(
                f"Iluminação muito baixa: {media:.2f} "
                f"(mínimo: {self.luz_minima})"
            )
        elif media > self.luz_maxima:
            problemas.append(
                f"Iluminação muito alta (posível reflexo): {media:.2f} "
                f"(máximo: {self.luz_maxima})"
            )

        # Score: quanto mais próximo do meio (0.5), melhor
        score = 1.0 - abs(media - 0.5) / 0.5
        score = max(0.0, min(1.0, score))

        return problemas, score

    def _validar_movimento(self, sessao: SessaoCaptura) -> tuple[list[str], float]:
        """Valida se há movimento suficiente (o sinalizante não ficou parado)."""
        if len(sessao.frames) < 2:
            return ["Poucos frames para detectar movimento"], 0.0

        avisos = []
        diferencas = []

        # Comparar frames consecutivos
        for i in range(1, min(len(sessao.frames), 30)):
            frame_anterior = self._bytes_para_frame(sessao.frames[i - 1].dados)
            frame_atual = self._bytes_para_frame(sessao.frames[i].dados)

            # Calcular diferença média
            diff = cv2.absdiff(frame_anterior, frame_atual)
            media_diff = np.mean(diff)
            diferencas.append(media_diff)

        if not diferencas:
            return ["Não foi possível detectar movimento"], 0.0

        media_movimento = np.mean(diferencas)

        if media_movimento < 5.0:
            avisos.append(
                f"Movimento muito baixo: {media_movimento:.1f} "
                "(sinalizante pode ter ficado parado)"
            )
            score = media_movimento / 5.0
        else:
            # Score baseado na variação do movimento (não pode ser muito monótono)
            std_movimento = np.std(diferencas)
            score = min(1.0, std_movimento / 50.0)

        return avisos, score

    def _bytes_para_frame(self, dados: bytes) -> np.ndarray:
        """Converte bytes PNG de volta para frame OpenCV."""
        import io

        nparr = np.frombuffer(dados, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return frame

"""Reconhecimento de Libras rodando na própria máquina.

Envolve o ``MotorKonectaV3``, que é quem faz extração real de landmarks com
MediaPipe (``mp.solutions.hands``) e classifica com os modelos produzidos pelo
SIGNLAB.

Escolha deliberada: local em vez de API. A câmera produz dezenas de frames por
segundo e um salto de rede por frame acrescentaria latência sem ganho enquanto o
motor roda na mesma máquina. A interface é a mesma de uma implementação remota,
então trocar depois não afeta o resto do sistema.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import numpy as np

from app_central.motors.motor_konecta_v3 import MotorKonectaV3
from app_central.providers.base import (
    ProviderIndisponivel,
    ResultadoTexto,
    SinaisParaTextoProvider,
)

logger = logging.getLogger(__name__)

# O motor devolve este rótulo quando não achou mãos no frame. Não é erro:
# a maior parte dos frames de uma conversa não tem sinal nenhum.
SEM_MAOS = "NO_HANDS"


class SinaisLocais(SinaisParaTextoProvider):
    """Implementação local de Libras → texto."""

    nome = "konecta_v3_local"

    def __init__(self, caminho_modelo: str = "models/v1"):
        self._caminho_modelo = Path(caminho_modelo)
        self._motor: Optional[MotorKonectaV3] = None

    def _obter_motor(self) -> MotorKonectaV3:
        if self._motor is None:
            self._motor = MotorKonectaV3(model_path=str(self._caminho_modelo))
        return self._motor

    async def disponivel(self) -> bool:
        """Sem modelo em disco não há o que reconhecer.

        Verificar isto explicitamente evita o modo de falha pior: o app parecer
        funcionando e nunca reconhecer nada. A UI usa esta resposta para mostrar
        o motor como indisponível (§11).
        """
        if not self._caminho_modelo.exists():
            logger.warning("Modelo ausente em %s", self._caminho_modelo)
            return False
        return any(self._caminho_modelo.iterdir())

    async def reconhecer(self, frame: np.ndarray) -> ResultadoTexto:
        inicio = time.monotonic()
        try:
            resultado = await self._obter_motor().process(frame)
        except Exception as erro:  # o motor não pode derrubar o app
            raise ProviderIndisponivel(f"motor local falhou: {erro}") from erro

        # "sem mãos no frame" é resposta legítima, não falha
        sem_sinal = resultado.signal == SEM_MAOS or resultado.status == "no_input"
        return ResultadoTexto(
            texto="" if sem_sinal else resultado.signal,
            confianca=0.0 if sem_sinal else resultado.confidence,
            latencia_ms=(time.monotonic() - inicio) * 1000,
            fonte=self.nome,
            detalhes={"status": resultado.status, "modelo": resultado.model_version},
        )

    async def encerrar(self) -> None:
        motor = self._motor
        self._motor = None
        fechar = getattr(motor, "close", None)
        if callable(fechar):
            fechar()

"""Descoberta de câmeras disponíveis.

Existe porque a pessoa que vai sinalizar precisa escolher entre a webcam do
notebook e uma externa — e nem sempre a externa é a 0. Sem essa escolha, o app
pega a primeira que responder, que costuma ser a errada quando há duas.

Sondar abrindo cada dispositivo é lento (cerca de 1s cada), então isto roda uma
vez e o resultado é reaproveitado.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)

MAX_INDICE = 4  # além disso, quase nunca há dispositivo real


@dataclass
class Camera:
    indice: int
    largura: int
    altura: int

    @property
    def rotulo(self) -> str:
        nome = "Webcam interna" if self.indice == 0 else f"Câmera {self.indice}"
        return f"{nome} — {self.largura}x{self.altura}"


def listar_cameras(maximo: int = MAX_INDICE) -> List[Camera]:
    """Abre cada índice e devolve os que entregam frame de verdade.

    Abrir não basta: no Windows um índice pode abrir e nunca entregar imagem.
    Só entra na lista quem realmente devolveu um frame.
    """
    import cv2

    encontradas: List[Camera] = []
    for indice in range(maximo):
        captura = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
        try:
            if not captura.isOpened():
                continue
            ok, frame = captura.read()
            if not ok or frame is None:
                continue
            altura, largura = frame.shape[:2]
            encontradas.append(Camera(indice=indice, largura=largura, altura=altura))
        except Exception as erro:
            logger.debug("Câmera %s indisponível: %s", indice, erro)
        finally:
            captura.release()

    logger.info("Câmeras encontradas: %s", [c.indice for c in encontradas] or "nenhuma")
    return encontradas

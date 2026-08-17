"""Transforma um fluxo de predições por frame em texto confirmado.

Lógica herdada do KONECTA V1 (``libras_recognizer.py``), que é a que se mostrou
utilizável na prática:

- **Limiar de confiança** — abaixo dele a predição é descartada.
- **Hold-to-confirm** — a mesma predição precisa persistir por um tempo antes de
  virar texto. Sem isso, a 15fps o reconhecedor cospe dezenas de palavras por
  segundo e a legenda fica ilegível.
- **Reset ao perder as mãos** — sinal novo começa do zero, sem herdar o anterior.
- **Sem repetir em seguida** — segurar a mão parada não deve escrever a mesma
  palavra várias vezes.

Fica separado do provider de propósito: o provider responde "o que é este
frame"; esta classe responde "o que a pessoa quis dizer".
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Confirmacao:
    """Uma predição que passou pelos critérios e virou texto."""

    texto: str
    confianca: float
    segurou_por_s: float


class Estabilizador:
    """Filtra ruído de predição frame a frame."""

    def __init__(
        self,
        limiar_confianca: float = 0.70,
        tempo_hold_s: float = 0.8,
        evitar_repeticao: bool = True,
    ):
        self.limiar_confianca = limiar_confianca
        self.tempo_hold_s = tempo_hold_s
        self.evitar_repeticao = evitar_repeticao
        self._candidato: Optional[str] = None
        self._desde: float = 0.0
        self._ultimo_confirmado: Optional[str] = None
        self.historico: List[str] = []

    def avaliar(
        self, texto: str, confianca: float, agora: Optional[float] = None
    ) -> Optional[Confirmacao]:
        """Processa uma predição. Devolve ``Confirmacao`` quando ela vira texto."""
        agora = time.monotonic() if agora is None else agora

        if not texto or confianca < self.limiar_confianca:
            # predição fraca não zera o candidato: um frame ruim no meio de um
            # sinal estável não deve obrigar a pessoa a recomeçar
            return None

        if texto != self._candidato:
            self._candidato = texto
            self._desde = agora
            return None

        segurou = agora - self._desde
        if segurou < self.tempo_hold_s:
            return None

        if self.evitar_repeticao and texto == self._ultimo_confirmado:
            return None

        self._candidato = None
        self._desde = 0.0
        self._ultimo_confirmado = texto
        self.historico.append(texto)
        logger.debug("Sinal confirmado: %s (%.0f%%)", texto, confianca * 100)
        return Confirmacao(texto=texto, confianca=confianca, segurou_por_s=segurou)

    def sem_maos(self) -> None:
        """Mãos saíram de quadro: o próximo sinal começa limpo."""
        self._candidato = None
        self._desde = 0.0
        self._ultimo_confirmado = None

    def texto_acumulado(self, separador: str = " ") -> str:
        return separador.join(self.historico)

    def limpar(self) -> None:
        self.sem_maos()
        self.historico.clear()

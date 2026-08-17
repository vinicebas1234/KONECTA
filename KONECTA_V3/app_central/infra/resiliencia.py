"""Retry, backoff e circuit breaker (§14 da spec).

Princípio: uma API fora do ar degrada a experiência, não derruba o app.

Por que circuit breaker e não só retry: quando o motor está fora, insistir a
cada frame gasta CPU, enche o log e faz a UI travar esperando timeout. Depois de
N falhas seguidas o circuito abre e as chamadas falham na hora, sem tocar a
rede, até uma janela de teste liberar uma tentativa.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from enum import Enum
from typing import Awaitable, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitoAberto(RuntimeError):
    """O circuito está aberto: nem tentamos, falhamos na hora."""


class EstadoCircuito(Enum):
    FECHADO = "fechado"      # tudo normal
    ABERTO = "aberto"        # falhando, nem tenta
    MEIO_ABERTO = "meio_aberto"  # deixa passar uma para testar


class CircuitBreaker:
    """Corta chamadas a um serviço que está falhando de forma consistente."""

    def __init__(
        self,
        nome: str,
        limite_falhas: int = 5,
        espera_s: float = 30.0,
    ):
        self.nome = nome
        self.limite_falhas = limite_falhas
        self.espera_s = espera_s
        self._falhas = 0
        self._aberto_em: Optional[float] = None

    @property
    def estado(self) -> EstadoCircuito:
        if self._aberto_em is None:
            return EstadoCircuito.FECHADO
        if time.monotonic() - self._aberto_em >= self.espera_s:
            return EstadoCircuito.MEIO_ABERTO
        return EstadoCircuito.ABERTO

    def registrar_sucesso(self) -> None:
        if self._falhas or self._aberto_em:
            logger.info("Circuito '%s' normalizado", self.nome)
        self._falhas = 0
        self._aberto_em = None

    def registrar_falha(self) -> None:
        self._falhas += 1
        if self._falhas >= self.limite_falhas and self._aberto_em is None:
            self._aberto_em = time.monotonic()
            logger.warning(
                "Circuito '%s' aberto após %s falhas; pausando %ss",
                self.nome,
                self._falhas,
                self.espera_s,
            )

    def permitir(self) -> bool:
        estado = self.estado
        if estado is EstadoCircuito.ABERTO:
            return False
        if estado is EstadoCircuito.MEIO_ABERTO:
            # deixa uma passar: se der certo, registrar_sucesso fecha o circuito
            self._aberto_em = time.monotonic()
        return True


async def com_retry(
    operacao: Callable[[], Awaitable[T]],
    tentativas: int = 3,
    espera_inicial_s: float = 0.2,
    espera_maxima_s: float = 5.0,
    breaker: Optional[CircuitBreaker] = None,
    descricao: str = "operação",
) -> T:
    """Executa ``operacao`` com backoff exponencial e jitter.

    O jitter evita que várias chamadas que falharam juntas voltem todas no mesmo
    instante e derrubem o serviço de novo assim que ele levanta.
    """
    if breaker is not None and not breaker.permitir():
        raise CircuitoAberto(f"{descricao}: motor indisponível, tentando novamente em instantes")

    espera = espera_inicial_s
    ultimo_erro: Optional[BaseException] = None

    for tentativa in range(1, max(1, tentativas) + 1):
        try:
            resultado = await operacao()
            if breaker is not None:
                breaker.registrar_sucesso()
            return resultado
        except asyncio.CancelledError:
            raise  # cancelamento é intenção do chamador, não falha a repetir
        except Exception as erro:
            ultimo_erro = erro
            if breaker is not None:
                breaker.registrar_falha()
            if tentativa >= tentativas:
                break
            atraso = min(espera, espera_maxima_s) * (0.5 + random.random())
            logger.info(
                "%s falhou (%s/%s): %s. Nova tentativa em %.1fs",
                descricao,
                tentativa,
                tentativas,
                erro,
                atraso,
            )
            await asyncio.sleep(atraso)
            espera *= 2

    raise RuntimeError(f"{descricao} falhou após {tentativas} tentativas") from ultimo_erro


MENSAGENS_AMIGAVEIS = {
    "timeout": "O motor de reconhecimento está demorando a responder.",
    "conexao": "Sem conexão com o motor de reconhecimento.",
    "circuito": "Motor de reconhecimento temporariamente indisponível.",
    "credencial": "Credencial do motor não configurada.",
    "modelo": "Modelo de reconhecimento não encontrado.",
}


def mensagem_amigavel(erro: BaseException) -> str:
    """Traduz exceção em frase para o usuário final (§14: nunca stack trace)."""
    if isinstance(erro, CircuitoAberto):
        return MENSAGENS_AMIGAVEIS["circuito"]
    if isinstance(erro, asyncio.TimeoutError):
        return MENSAGENS_AMIGAVEIS["timeout"]
    texto = str(erro).lower()
    if "credencial" in texto or "api key" in texto or "unauthorized" in texto:
        return MENSAGENS_AMIGAVEIS["credencial"]
    if "modelo" in texto or "model" in texto:
        return MENSAGENS_AMIGAVEIS["modelo"]
    if "conex" in texto or "connect" in texto or "refused" in texto:
        return MENSAGENS_AMIGAVEIS["conexao"]
    return MENSAGENS_AMIGAVEIS["circuito"]

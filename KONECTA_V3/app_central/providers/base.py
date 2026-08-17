"""Contratos dos motores de IA (§7 da spec).

O núcleo do KONECTA fala com estas interfaces e nunca com um fornecedor
específico. Trocar de motor é registrar outra implementação; nada mais no
sistema muda.

Uma implementação pode ser local (roda na máquina) ou remota (chama uma API).
A interface é a mesma de propósito: hoje o reconhecimento de Libras roda
embutido para evitar um salto de rede por frame, e migrar para API depois é
escrever outra classe aqui, sem tocar em UI, sessão ou pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class ResultadoTexto:
    """Texto reconhecido a partir de áudio ou de sinais."""

    texto: str
    confianca: float
    latencia_ms: float
    fonte: str  # qual provider produziu
    parcial: bool = False  # True enquanto a frase ainda não fechou
    detalhes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResultadoSinais:
    """Representação em Libras produzida a partir de texto."""

    glosa: str
    texto_origem: str
    latencia_ms: float
    fonte: str
    detalhes: Dict[str, Any] = field(default_factory=dict)


class ProviderIndisponivel(RuntimeError):
    """O motor não pôde atender agora (rede, credencial, modelo ausente).

    Erro esperado e recuperável: quem chama deve degradar com elegância, não
    quebrar. Nunca deve chegar ao usuário final como stack trace (§14).
    """


class Provider(ABC):
    """Base comum: todo motor sabe dizer se está utilizável."""

    nome: str = "desconhecido"

    async def disponivel(self) -> bool:
        """Checagem barata de saúde, para a UI mostrar o estado do motor (§11)."""
        return True

    async def encerrar(self) -> None:
        """Libera recursos (conexões, modelos). Idempotente."""


class AudioParaTextoProvider(Provider):
    """Áudio do usuário ouvinte → texto."""

    @abstractmethod
    async def transcrever(self, audio: np.ndarray, taxa_amostragem: int) -> ResultadoTexto:
        """Transcreve um bloco de áudio mono float32."""


class SinaisParaTextoProvider(Provider):
    """Sinais em Libras do usuário surdo → texto."""

    @abstractmethod
    async def reconhecer(self, frame: np.ndarray) -> ResultadoTexto:
        """Reconhece um frame BGR e devolve o texto correspondente."""

    async def reconhecer_sequencia(self, frames: List[np.ndarray]) -> ResultadoTexto:
        """Reconhece uma sequência (sinais dinâmicos).

        Implementação padrão usa o último frame. Motores com modelo temporal
        devem sobrescrever — um sinal dinâmico não é definido por um frame só.
        """
        if not frames:
            raise ProviderIndisponivel("sequência vazia")
        return await self.reconhecer(frames[-1])


class TextoParaSinaisProvider(Provider):
    """Texto → representação em Libras (avatar)."""

    @abstractmethod
    async def sinalizar(self, texto: str) -> ResultadoSinais:
        """Envia o texto para ser sinalizado."""


@dataclass
class Motores:
    """Os três motores que o núcleo usa. Qualquer um pode estar ausente.

    Ausente é estado normal, não erro: um usuário ouvinte não precisa do motor
    de Libras→texto, e vice-versa.
    """

    audio_para_texto: Optional[AudioParaTextoProvider] = None
    sinais_para_texto: Optional[SinaisParaTextoProvider] = None
    texto_para_sinais: Optional[TextoParaSinaisProvider] = None

    async def encerrar(self) -> None:
        for provider in (self.audio_para_texto, self.sinais_para_texto, self.texto_para_sinais):
            if provider is not None:
                await provider.encerrar()

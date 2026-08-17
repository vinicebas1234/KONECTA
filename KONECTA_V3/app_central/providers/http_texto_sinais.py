"""Texto → Libras via TEXTO_PARA_LIBRAS (avatar VLibras).

Fala o contrato do serviço central do Konecta: ``POST /publicar`` com
``{origem, tipo, texto}``. O TEXTO_PARA_LIBRAS já implementa esse endpoint e
entrega o texto ao avatar 3D — este provider só o consome, não reimplementa
nada.

Só ``tipo="final"`` vira sinal: parciais mudam a cada fração de segundo e
cortariam a animação no meio.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import aiohttp

from app_central.infra.resiliencia import CircuitBreaker, com_retry
from app_central.providers.base import (
    ProviderIndisponivel,
    ResultadoSinais,
    TextoParaSinaisProvider,
)

logger = logging.getLogger(__name__)


class TextoParaSinaisHTTP(TextoParaSinaisProvider):
    """Cliente do TEXTO_PARA_LIBRAS."""

    nome = "texto_para_libras_http"

    def __init__(
        self,
        url_base: str = "http://127.0.0.1:8300",
        timeout_s: float = 5.0,
        tentativas: int = 3,
    ):
        self.url_base = url_base.rstrip("/")
        self.timeout_s = timeout_s
        self.tentativas = tentativas
        self._sessao: Optional[aiohttp.ClientSession] = None
        self._breaker = CircuitBreaker(nome=self.nome, limite_falhas=3, espera_s=20.0)

    async def _obter_sessao(self) -> aiohttp.ClientSession:
        if self._sessao is None or self._sessao.closed:
            self._sessao = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_s)
            )
        return self._sessao

    async def disponivel(self) -> bool:
        """Bate na página do serviço. Falha aqui é resposta, não exceção.

        Usa sessão própria e descartável: uma checagem de saúde não deve abrir
        conexão persistente, senão só perguntar "está no ar?" já vaza recurso
        em quem nunca chega a enviar texto.
        """
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=2)
            ) as sessao:
                async with sessao.get(f"{self.url_base}/") as resposta:
                    return resposta.status == 200
        except Exception:
            return False

    async def sinalizar(self, texto: str) -> ResultadoSinais:
        texto = (texto or "").strip()
        if not texto:
            raise ProviderIndisponivel("texto vazio")

        inicio = time.monotonic()
        corpo = {"origem": "audio", "tipo": "final", "texto": texto}

        async def _enviar() -> None:
            sessao = await self._obter_sessao()
            async with sessao.post(f"{self.url_base}/publicar", json=corpo) as resposta:
                if resposta.status >= 400:
                    raise RuntimeError(f"HTTP {resposta.status}")

        try:
            await com_retry(
                _enviar,
                tentativas=self.tentativas,
                breaker=self._breaker,
                descricao="envio ao avatar",
            )
        except Exception as erro:
            raise ProviderIndisponivel(str(erro)) from erro

        return ResultadoSinais(
            glosa="",  # a glosa é resolvida do lado do avatar, pela API do VLibras
            texto_origem=texto,
            latencia_ms=(time.monotonic() - inicio) * 1000,
            fonte=self.nome,
        )

    async def encerrar(self) -> None:
        if self._sessao is not None and not self._sessao.closed:
            await self._sessao.close()
        self._sessao = None

"""Gerenciador de datasets — carregamento, cache, versionamento.

Centraliza a lógica de acesso aos datasets, abstraindo as fontes e
permitindo que o Knowledge Engine carregue amostras de forma transparente.
"""

from __future__ import annotations

import threading
from typing import Optional

from core.types import Amostra
from backend.dataset import source as ds_source


class DatasetManager:
    """Orquestrador de datasets com cache em memória."""

    def __init__(self):
        self._cache: dict[str, list[Amostra]] = {}
        self._lock = threading.Lock()

    def listar(
        self,
        fonte: str,
        limite_sinais: Optional[int] = None,
        usar_cache: bool = True,
    ) -> list[Amostra]:
        """Carrega amostras de uma fonte, opcionalmente do cache."""
        chave_cache = f"{fonte}:{limite_sinais}"

        if usar_cache and chave_cache in self._cache:
            return self._cache[chave_cache]

        fonte_obj = ds_source.obter_fonte(fonte)
        if fonte_obj is None:
            raise ValueError(f"Fonte '{fonte}' não disponível")

        amostras = fonte_obj.listar(limite_sinais)

        if usar_cache:
            with self._lock:
                self._cache[chave_cache] = amostras

        return amostras

    def limpar_cache(self, fonte: Optional[str] = None) -> None:
        """Limpa o cache, opcionalmente de uma fonte específica."""
        with self._lock:
            if fonte:
                prefixo = f"{fonte}:"
                self._cache = {
                    k: v for k, v in self._cache.items() if not k.startswith(prefixo)
                }
            else:
                self._cache.clear()

    def contar(self, fonte: str) -> dict:
        """Retorna estatísticas de uma fonte sem carregar as amostras."""
        fonte_obj = ds_source.obter_fonte(fonte)
        if fonte_obj is None:
            raise ValueError(f"Fonte '{fonte}' não disponível")
        return fonte_obj.contar()

    def fontes_disponiveis(self) -> dict[str, bool]:
        """Lista todas as fontes e sua disponibilidade."""
        return ds_source.fontes_disponiveis()


# Singleton global
_manager = DatasetManager()


def listar(
    fonte: str,
    limite_sinais: Optional[int] = None,
    usar_cache: bool = True,
) -> list[Amostra]:
    """Carrega amostras de uma fonte via gerenciador global."""
    return _manager.listar(fonte, limite_sinais, usar_cache)


def contar(fonte: str) -> dict:
    """Retorna estatísticas de uma fonte."""
    return _manager.contar(fonte)


def fontes_disponiveis() -> dict[str, bool]:
    """Lista todas as fontes e sua disponibilidade."""
    return _manager.fontes_disponiveis()


def limpar_cache(fonte: Optional[str] = None) -> None:
    """Limpa o cache de amostras."""
    _manager.limpar_cache(fonte)

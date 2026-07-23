"""Abstração de fontes de dados — V1, V2 nativa, sintética.

Cada fonte implementa um contrato de leitura comum: listar amostras com
metadados e carregá-las sob demanda.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from core.types import Amostra


class DatasetSource(ABC):
    """Contrato que toda fonte de dataset deve implementar."""

    @abstractmethod
    def listar(self, limite_sinais: Optional[int] = None) -> list[Amostra]:
        """Retorna todas as amostras da fonte, opcionalmente limitadas."""

    @abstractmethod
    def contar(self) -> dict:
        """Retorna estatísticas da fonte: {sinais: int, sinalizantes: int, amostras: int}."""

    @property
    @abstractmethod
    def nome(self) -> str:
        """Nome único da fonte."""

    @property
    @abstractmethod
    def disponivel(self) -> bool:
        """Verifica se a fonte está pronta para uso (caminhos existem, etc)."""


class V1DynamicSource(DatasetSource):
    """Adaptador somente leitura do dataset V1 — sinais dinâmicos."""

    @property
    def nome(self) -> str:
        return "v1_dinamicos"

    @property
    def disponivel(self) -> bool:
        from backend.services.dataset_provider import fontes_disponiveis
        return fontes_disponiveis()["v1_dinamicos"]

    def listar(self, limite_sinais: Optional[int] = None) -> list[Amostra]:
        from backend.services.dataset_provider import carregar_v1_dinamicos
        return carregar_v1_dinamicos(limite_sinais)

    def contar(self) -> dict:
        from backend.services.dataset_provider import carregar_v1_dinamicos
        amostras = carregar_v1_dinamicos()
        return {
            "amostras": len(amostras),
            "sinais": len({a.sinal for a in amostras}),
            "sinalizantes": len({a.sinalizante for a in amostras}),
        }


class V1StaticSource(DatasetSource):
    """Adaptador somente leitura do dataset V1 — sinais estáticos."""

    @property
    def nome(self) -> str:
        return "v1_estaticos"

    @property
    def disponivel(self) -> bool:
        from backend.services.dataset_provider import fontes_disponiveis
        return fontes_disponiveis()["v1_estaticos"]

    def listar(self, limite_sinais: Optional[int] = None) -> list[Amostra]:
        from backend.services.dataset_provider import carregar_v1_estaticos
        return carregar_v1_estaticos(limite_sinais)

    def contar(self) -> dict:
        from backend.services.dataset_provider import carregar_v1_estaticos
        amostras = carregar_v1_estaticos()
        return {
            "amostras": len(amostras),
            "sinais": len({a.sinal for a in amostras}),
            "sinalizantes": len({a.sinalizante for a in amostras}),
        }


class SyntheticSource(DatasetSource):
    """Dataset sintético pequeno para demonstração e testes."""

    @property
    def nome(self) -> str:
        return "sintetico"

    @property
    def disponivel(self) -> bool:
        return True

    def listar(self, limite_sinais: Optional[int] = None) -> list[Amostra]:
        from backend.services.dataset_provider import gerar_sintetico
        amostras = gerar_sintetico()
        if limite_sinais:
            sinais_unicos = sorted({a.sinal for a in amostras})[:limite_sinais]
            return [a for a in amostras if a.sinal in sinais_unicos]
        return amostras

    def contar(self) -> dict:
        from backend.services.dataset_provider import gerar_sintetico
        amostras = gerar_sintetico()
        return {
            "amostras": len(amostras),
            "sinais": len({a.sinal for a in amostras}),
            "sinalizantes": len({a.sinalizante for a in amostras}),
        }


# Registro global de fontes disponíveis
SOURCES = {
    "v1_dinamicos": V1DynamicSource(),
    "v1_estaticos": V1StaticSource(),
    "sintetico": SyntheticSource(),
}


def obter_fonte(nome: str) -> Optional[DatasetSource]:
    """Obtém uma fonte pelo nome, se disponível."""
    if nome not in SOURCES:
        return None
    fonte = SOURCES[nome]
    return fonte if fonte.disponivel else None


def fontes_disponiveis() -> dict[str, bool]:
    """Lista todas as fontes e sua disponibilidade."""
    return {nome: fonte.disponivel for nome, fonte in SOURCES.items()}

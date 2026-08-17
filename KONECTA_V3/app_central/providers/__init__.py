"""Motores de IA atrás de contratos estáveis (§7 da spec).

O núcleo importa daqui e nunca de um fornecedor específico.
"""

from app_central.providers.base import (
    AudioParaTextoProvider,
    Motores,
    Provider,
    ProviderIndisponivel,
    ResultadoSinais,
    ResultadoTexto,
    SinaisParaTextoProvider,
    TextoParaSinaisProvider,
)

__all__ = [
    "AudioParaTextoProvider",
    "Motores",
    "Provider",
    "ProviderIndisponivel",
    "ResultadoSinais",
    "ResultadoTexto",
    "SinaisParaTextoProvider",
    "TextoParaSinaisProvider",
]

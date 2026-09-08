"""Configuração do Libras Learning Agent (LLA).

Prefixo de env var: ``LLA_`` — deliberadamente diferente de ``KONECTA_``
(usado por ``app_central/core/config.py``) para não colidir com a config do
resto do projeto.

Isolamento (o ponto mais importante deste módulo): os defaults de
``models_dir`` e ``database_url`` apontam para dentro de
``libras_learning_agent/``, nunca para ``KONECTA_V3/models/`` (auto-discovery
de modelos de produção, ver ``KONECTA_V3/models/LEIA-ME.md``) nem para o
banco do ``app_backend``. `tests/test_foundation.py` prova isso.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# libras_learning_agent/core/config.py -> parents[1] == libras_learning_agent/
PACKAGE_DIR = Path(__file__).resolve().parents[1]

_MASK = "***REDACTED***"
# Campos que nunca podem aparecer em texto puro em repr/str/model_dump.
_SECRET_FIELDS = frozenset({"anthropic_api_key", "gemini_api_key"})


class Settings(BaseSettings):
    """Configuração do LLA, lida de variáveis de ambiente / ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="LLA_",
        env_file=str(PACKAGE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Permite passar tanto o nome do campo (anthropic_api_key, ex. em
        # testes/código Python) quanto o alias (ANTHROPIC_API_KEY, env var).
        populate_by_name=True,
    )

    # --- Banco de dados --- caminho relativo à raiz do KONECTA_V3
    database_url: str = "sqlite:///./libras_learning_agent/data/agent.db"

    # --- Diretórios próprios do agente ---
    data_dir: str = "./libras_learning_agent/data"
    # NUNCA apontar para KONECTA_V3/models/ — ver docstring do módulo.
    models_dir: str = "./libras_learning_agent/models"

    # --- Logging ---
    log_level: str = "INFO"
    log_dir: str = "./libras_learning_agent/logs"

    # --- API HTTP (Ciclo 6) --- porta própria, nunca 8000 (app_backend/vision_lab
    # já usam essa porta) — ver api/app.py.
    api_port: int = 8010

    # --- Anthropic --- reaproveita a env var já usada no resto do projeto,
    # por isso o alias explícito ignora o prefixo LLA_.
    anthropic_api_key: Optional[str] = Field(
        default=None, validation_alias="ANTHROPIC_API_KEY"
    )

    # --- Gemini --- camada de comparação de fontes (Ciclo 4) usa o tier
    # gratuito do Google Gemini, não a Anthropic — mesmo padrão de alias
    # explícito ignorando o prefixo LLA_.
    gemini_api_key: Optional[str] = Field(
        default=None, validation_alias="GEMINI_API_KEY"
    )

    # --- Cache de compare_sources (Ciclo 12) --- TTL em dias para uma entrada
    # de cache em `research/cache.py` (sob `data_dir/compare_cache/`) ser
    # considerada válida. 7 dias por padrão: a relação entre fontes sobre um
    # conceito de Libras não muda de um dia para o outro, mas é ajustável via
    # LLA_COMPARE_CACHE_TTL_DAYS se o projeto decidir outro valor.
    compare_cache_ttl_days: int = 7

    # --- Segurança: mascaramento de segredos -----------------------------
    #
    # Requisito: logar o objeto Settings inteiro por engano nunca pode expor
    # anthropic_api_key em texto puro. __repr__/__str__/model_dump são
    # sobrescritos para sempre mascarar, independentemente de quem chama.

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        data = super().model_dump(**kwargs)
        for field in _SECRET_FIELDS:
            if data.get(field):
                data[field] = _MASK
        return data

    def __repr__(self) -> str:
        masked = self.model_dump()
        fields = ", ".join(f"{k}={v!r}" for k, v in masked.items())
        return f"Settings({fields})"

    __str__ = __repr__


@lru_cache
def get_settings() -> Settings:
    return Settings()

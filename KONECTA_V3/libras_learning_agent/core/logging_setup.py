"""Logging estruturado (JSON) do Libras Learning Agent.

Requisito de segurança: nenhum log pode conter uma chave de API em texto
puro — nem via ``Settings.__repr__`` (já mascarado em ``core/config.py``),
nem via uma string solta que tenha cara de chave (ex. alguém logando
``ANTHROPIC_API_KEY`` bruta por engano). O formatter aqui redige qualquer
string que bata com o padrão ``sk-...`` como camada extra de proteção.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from libras_learning_agent.core.config import Settings

LOGGER_NAME = "libras_learning_agent"

_REDACTED = "***REDACTED***"
# ponytail: heurística por prefixo (sk-/sk-ant-, no estilo Anthropic/OpenAI).
# Não pega todo formato de chave possível — ampliar o padrão se outro provedor
# com formato diferente entrar em cena.
_API_KEY_PATTERN = re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_\-]{10,}\b")

# Atributos padrão de um LogRecord — usado para achar os campos extras que o
# chamador passou via `extra={...}`, calculado a partir do stdlib (não
# hardcoded) para não ficar desatualizado entre versões do Python.
_STANDARD_RECORD_FIELDS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
) | {"message", "asctime"}


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return _API_KEY_PATTERN.sub(_REDACTED, value)
    return value


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "event", record.name),
            "message": _redact(record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_FIELDS or key == "event":
                continue
            payload[key] = _redact(value)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(settings: "Settings") -> logging.Logger:
    """Configura o logger ``libras_learning_agent`` (arquivo JSON em ``settings.log_dir``)."""
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(settings.log_level)
    logger.handlers.clear()
    logger.propagate = False

    handler = logging.FileHandler(log_dir / "agent.log", encoding="utf-8")
    handler.setFormatter(_JsonFormatter())
    logger.addHandler(handler)

    return logger

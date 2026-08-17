"""Autenticação via API key (header X-API-Key)."""

from __future__ import annotations

import hashlib
import hmac
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, Request, status

from app_backend.config import settings


def hash_api_key(raw_key: str) -> str:
    """Hash SHA-256 de uma API key (para armazenamento em users.api_key_hash)."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _key_matches(provided: str, expected: str) -> bool:
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def is_valid_api_key(provided: str | None) -> bool:
    if not provided:
        return False
    for key in settings.active_api_keys:
        if _key_matches(provided, key):
            return True
    return False


async def require_api_key(
    request: Request,
    x_api_key: Annotated[Optional[str], Header(alias="X-API-Key")] = None,
) -> str:
    """Dependência: exige X-API-Key válida. Usada em rotas protegidas."""
    header_name = settings.api_key_header
    # Aceita o alias configurado além do padrão.
    key = x_api_key or request.headers.get(header_name)
    if not is_valid_api_key(key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida ou ausente. Envie o header X-API-Key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return key  # type: ignore[return-value]


async def optional_api_key(
    request: Request,
    x_api_key: Annotated[Optional[str], Header(alias="X-API-Key")] = None,
) -> Optional[str]:
    """Dependência opcional: valida se presente, senão None."""
    header_name = settings.api_key_header
    key = x_api_key or request.headers.get(header_name)
    if key is None:
        return None
    if not is_valid_api_key(key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return key


# Type aliases for FastAPI Depends
RequireAPIKey = Annotated[str, Depends(require_api_key)]
OptionalAPIKey = Annotated[Optional[str], Depends(optional_api_key)]

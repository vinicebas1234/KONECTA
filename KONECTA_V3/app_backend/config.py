"""Configuração centralizada via variáveis de ambiente / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Runtime settings for the KONECTA backend."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Core ---
    app_name: str = "KONECTA Intelligence Hub API"
    app_version: str = "1.0.0"
    environment: str = "development"  # development | staging | production
    debug: bool = False
    api_prefix: str = "/api"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    log_level: str = "INFO"

    # --- Database ---
    # SQLite (dev):  sqlite:///./data/konecta.db
    # PostgreSQL:    postgresql+psycopg2://user:pass@localhost:5432/konecta
    database_url: str = Field(
        default="sqlite:///" + str(BASE_DIR / "data" / "konecta.db").replace("\\", "/"),
        description="SQLAlchemy connection string",
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_pre_ping: bool = True
    db_echo: bool = False

    # --- Security / Auth ---
    api_key_header: str = "X-API-Key"
    # Chave principal para N8N e clientes automatizados (env: KONECTA_API_KEY).
    konecta_api_key: str = "dev-konecta-api-key-change-me"
    # Chaves extras (CSV) além de KONECTA_API_KEY.
    api_keys: str = ""
    rate_limit: str = "100/minute"
    rate_limit_auth: str = "1000/minute"

    # --- CORS (env: CORS_ORIGINS) ---
    cors_origins: str = (
        "http://localhost:3000,http://localhost:5173,"
        "http://localhost:8000,http://127.0.0.1:8000"
    )
    cors_methods: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    cors_headers: str = "*"

    # --- Logging / Monitoring ---
    log_json: bool = True
    log_dir: str = str(BASE_DIR / "logs")
    sentry_dsn: Optional[str] = None
    prometheus_enabled: bool = True
    default_tags: str = ""

    # --- Signals ---
    signals_default_page_size: int = 50
    signals_max_page_size: int = 500

    # --- Backup ---
    backup_dir: str = str(BASE_DIR / "backups")
    backup_retention_days: int = 14

    # --- Proxy ---
    trusted_proxy: bool = True

    # --- Derived helpers -------------------------------------------------

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cors_methods_list(self) -> List[str]:
        return [m.strip() for m in self.cors_methods.split(",") if m.strip()]

    @property
    def cors_headers_list(self) -> List[str]:
        return [h.strip() for h in self.cors_headers.split(",") if h.strip()]

    @property
    def active_api_keys(self) -> List[str]:
        keys = [self.konecta_api_key] if self.konecta_api_key else []
        keys.extend(k.strip() for k in self.api_keys.split(",") if k.strip())
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: List[str] = []
        for k in keys:
            if k not in seen:
                seen.add(k)
                unique.append(k)
        return unique

    @property
    def tag_list(self) -> List[str]:
        return [t.strip() for t in self.default_tags.split(",") if t.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def sqlite_path(self) -> Optional[Path]:
        """Return the SQLite file path when using a sqlite URL, else None."""
        url = self.database_url
        if url.startswith("sqlite"):
            prefix = "sqlite:///"
            if url.startswith(prefix):
                return Path(url[len(prefix) :])
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

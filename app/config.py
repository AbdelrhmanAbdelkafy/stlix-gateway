"""Application settings, loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = parent of the `app` package. Load .env from here so settings
# resolve no matter what working directory the server is launched from.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    # --- Gateway ---
    app_name: str = "Stlix Gateway"
    app_env: str = Field(default="dev", description="dev | staging | prod")
    # Shared secret clients must send as `X-API-Key`. Empty string disables the check.
    gateway_api_key: str = Field(default="")

    # --- Nama ERP REST v1 ---
    # Cloud: https://stlixvalley.namasoft.net/erp/rest/v1
    # Local: http://localhost:8080/erp/rest/v1
    nama_base_url: str = Field(default="https://stlixvalley.namasoft.net/erp/rest/v1")
    nama_client_id: str = Field(default="")
    nama_client_secret: str = Field(default="")
    nama_timeout: float = Field(default=30.0)
    # Connector mode: read_only (default, safe) | read_write
    nama_mode: str = Field(default="read_only")

    @property
    def nama_base(self) -> str:
        return self.nama_base_url.rstrip("/")

    @property
    def nama_configured(self) -> bool:
        return bool(self.nama_client_id and self.nama_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()

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
    # Additional accepted keys (comma-separated), on top of gateway_api_key.
    gateway_api_keys: str = Field(default="")

    # --- Layer 6: logs / monitoring / security ---
    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=True)
    # Fixed-window requests/minute per client (0 = disabled).
    rate_limit_per_minute: int = Field(default=120)
    # Comma-separated allowed CORS origins ("*" = any).
    cors_origins: str = Field(default="*")
    security_headers: bool = Field(default=True)

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()] or ["*"]

    @property
    def api_keys(self) -> set[str]:
        keys = {k.strip() for k in self.gateway_api_keys.split(",") if k.strip()}
        if self.gateway_api_key:
            keys.add(self.gateway_api_key)
        return keys

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

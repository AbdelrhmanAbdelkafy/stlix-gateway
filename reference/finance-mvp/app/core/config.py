"""Application configuration (Chapter 35: Environment Configuration).

All settings come from the environment. Defaults use SQLite so the app runs
out-of-the-box; docker-compose injects the MySQL URL for the real stack.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_name: str = "Finance OS MVP"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    # --- Database (Ch. 41/42) ---
    # Example MySQL URL: mysql+pymysql://finance:finance@db:3306/finance_os
    database_url: str = "sqlite:///./finance_mvp.db"

    # --- Security / Auth (Ch. 24-27) ---
    jwt_secret: str = "change-me-in-production-please-32-bytes-min"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # --- Cache (optional, Ch. 10) ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Seed bootstrap admin ---
    seed_admin_email: str = "admin@finance.local"
    seed_admin_password: str = "Admin#12345"


settings = Settings()

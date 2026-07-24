"""Gateway-level auth: optional shared X-API-Key (one or many keys)."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from ..config import Settings, get_settings


def require_api_key(
    x_api_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Enforce X-API-Key only when at least one key is configured (else no-op).

    Accepts any key in GATEWAY_API_KEY or the comma-separated GATEWAY_API_KEYS.
    """
    keys = settings.api_keys
    if not keys:
        return
    if x_api_key not in keys:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing X-API-Key."
        )

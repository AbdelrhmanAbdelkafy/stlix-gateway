"""Gateway-level auth: optional shared X-API-Key for clients."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from ..config import Settings, get_settings


def require_api_key(
    x_api_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Enforce X-API-Key only when GATEWAY_API_KEY is set (else no-op)."""
    if not settings.gateway_api_key:
        return
    if x_api_key != settings.gateway_api_key:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing X-API-Key."
        )

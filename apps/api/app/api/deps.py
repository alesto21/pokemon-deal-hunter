from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """If API_KEY is configured, every /api/v1 request must carry it (the web server adds it)."""
    expected = get_settings().api_key
    if expected is None or not expected.get_secret_value():
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, expected.get_secret_value()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key")

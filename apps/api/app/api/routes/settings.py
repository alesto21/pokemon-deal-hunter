from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings, get_user_config
from app.notifications.telegram import TelegramNotifier

router = APIRouter(tags=["settings"])


@router.get("/settings")
def settings() -> dict:
    """Effective configuration. Secrets are reported only as configured / not configured."""
    s = get_settings()
    return {
        "environment": s.environment,
        "config_dir": str(s.config_dir),
        "secrets": {
            "cardtrader_api_token": bool(s.cardtrader_api_token and s.cardtrader_api_token.get_secret_value()),
            "telegram_bot_token": bool(s.telegram_bot_token and s.telegram_bot_token.get_secret_value()),
            "telegram_chat_id": bool(s.telegram_chat_id),
            "api_key": bool(s.api_key and s.api_key.get_secret_value()),
        },
        "modes": {"cardtrader": "mock" if s.cardtrader_is_mock else "live",
                  "telegram": "dry-run" if s.telegram_is_dry_run else "live"},
        "user_config": get_user_config().model_dump(mode="json"),
    }


@router.post("/telegram/test")
def telegram_test() -> dict:
    res = TelegramNotifier().send("✅ <b>Pokémon Deal Hunter</b>: Telegram test message.")
    return res.__dict__

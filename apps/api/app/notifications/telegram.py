"""Telegram Bot API client with dry-run mode (no token → messages are logged, not sent)."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger, redact_text

log = get_logger(__name__)


@dataclass
class SendResult:
    ok: bool
    message_id: int | None
    dry_run: bool
    error: str | None = None


class TelegramNotifier:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        s = get_settings()
        self.dry_run = s.telegram_is_dry_run
        self.chat_id = s.telegram_chat_id
        self._token = s.telegram_bot_token.get_secret_value() if s.telegram_bot_token else ""
        self._transport = transport

    def send(self, text: str, button_url: str | None = None, button_text: str = "Open listing") -> SendResult:
        if self.dry_run:
            log.info("telegram_dry_run", preview=text[:400])
            return SendResult(True, None, True)
        payload: dict = {
            "chat_id": self.chat_id,
            "text": text[:4096],
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if button_url:
            payload["reply_markup"] = {"inline_keyboard": [[{"text": button_text, "url": button_url}]]}
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        try:
            with httpx.Client(timeout=15, transport=self._transport) as client:
                resp = client.post(url, json=payload)
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            err = redact_text(f"{type(exc).__name__}: {exc}")
            log.error("telegram_send_failed", error=err)
            return SendResult(False, None, False, err)
        if not data.get("ok"):
            err = redact_text(str(data.get("description", "unknown error")))
            log.error("telegram_send_failed", error=err)
            return SendResult(False, None, False, err)
        return SendResult(True, data["result"]["message_id"], False)

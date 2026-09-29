"""Structured logging with secret redaction."""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

_SECRET_KEYS = re.compile(r"(token|secret|password|api_key|authorization|chat_id)", re.I)
# Telegram bot tokens and bearer tokens inside free text (e.g. exception messages / URLs).
_SECRET_PATTERNS = [
    re.compile(r"bot\d{5,}:[A-Za-z0-9_-]{20,}"),
    re.compile(r"(Bearer\s+)[A-Za-z0-9._-]{10,}", re.I),
]


def redact_text(text: str) -> str:
    for pat in _SECRET_PATTERNS:
        text = pat.sub(lambda m: (m.group(1) if m.groups() else "") + "***REDACTED***", text)
    return text


def _redact(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key, value in list(event_dict.items()):
        if _SECRET_KEYS.search(key) and value is not None:
            event_dict[key] = "***REDACTED***"
        elif isinstance(value, str):
            event_dict[key] = redact_text(value)
    return event_dict


def configure_logging(level: str = "INFO", json: bool = False) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper())
    # httpx logs full URLs at INFO (Telegram URLs contain the bot token).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    renderer = structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer(colors=False)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level.upper())),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)

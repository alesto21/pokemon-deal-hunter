from __future__ import annotations

import os
import tempfile

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ["CARDTRADER_MOCK"] = "true"
os.environ["TELEGRAM_DRY_RUN"] = "true"
# Explicit empty values override anything in a developer's local .env file.
for _secret in ("API_KEY", "CARDTRADER_API_TOKEN", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
    os.environ[_secret] = ""
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="pdh-test-")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import UserConfig, get_settings, get_user_config
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.session import set_engine
from app.notifications.telegram import SendResult

get_settings.cache_clear()


@pytest.fixture()
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    set_engine(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine) -> Session:
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    yield s
    s.rollback()
    s.close()


@pytest.fixture()
def cfg() -> UserConfig:
    return get_user_config().model_copy(deep=True)


class FakeNotifier:
    """Records messages instead of calling Telegram."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str | None]] = []
        self.dry_run = False

    def send(self, text: str, button_url: str | None = None, button_text: str = "Open listing") -> SendResult:
        self.sent.append((text, button_url))
        return SendResult(True, len(self.sent), False)


@pytest.fixture()
def notifier() -> FakeNotifier:
    return FakeNotifier()

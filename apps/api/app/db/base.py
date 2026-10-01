from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def utc_today() -> date:
    """Price-history days are UTC days (snapshots are stored in UTC). Never use date.today() for
    them: containers run in Europe/Oslo, and the local date is a day ahead between 00:00 and
    02:00, which previously made scans in that window aggregate the wrong day."""
    return datetime.now(UTC).date()


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)

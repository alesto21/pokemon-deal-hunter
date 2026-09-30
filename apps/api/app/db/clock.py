"""Authoritative time for cross-process coordination (scan locks, schedule health).

Process clocks can drift apart; the database clock is shared by every process, so lock
acquisition, heartbeats, staleness and schedule health all use it.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

_QUERIES = {
    "postgresql": "SELECT timezone('utc', clock_timestamp())",
    "sqlite": "SELECT strftime('%Y-%m-%d %H:%M:%f', 'now')",
}


def db_now(session: Session) -> datetime:
    """Current database time as a naive UTC datetime (the convention used by all models)."""
    dialect = session.get_bind().dialect.name
    query = _QUERIES.get(dialect)
    if query is None:
        raise RuntimeError(f"db_now() does not support the {dialect} dialect")
    value = session.execute(text(query)).scalar_one()
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.replace(tzinfo=None)

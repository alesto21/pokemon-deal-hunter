"""Per-source scan locks stored in ``source_status``.

* acquire: one atomic conditional UPDATE — succeeds only if the lock is free or stale.
* heartbeat: a running scan refreshes ``lock_heartbeat_at``; staleness is measured from the
  last heartbeat, so a long but alive scan is never reclaimed.
* release: only the owner can release (``WHERE lock_owner = me``).
* recovery: on worker start, stale locks — and locks of a previous worker process on this
  same host, which is certainly dead — are released and logged.
* time: every timestamp and age comes from the database clock (``db.clock.db_now``), never from
  a process clock, so clock drift between processes cannot make a lock look fresh or stale.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select, update

from app.core.config import get_user_config
from app.core.logging import get_logger
from app.db.clock import db_now
from app.db.models import SourceStatus
from app.db.session import session_scope
from app.services.lifecycle import owner_id, same_host_worker_prefix

log = get_logger(__name__)


def stale_after() -> timedelta:
    return timedelta(minutes=get_user_config().sources.scheduler.scan_lock_stale_minutes)


def heartbeat_interval() -> float:
    return get_user_config().sources.scheduler.scan_lock_heartbeat_seconds


@dataclass
class LockInfo:
    locked: bool
    owner: str | None = None
    acquired_at: datetime | None = None
    heartbeat_at: datetime | None = None
    age_seconds: float | None = None
    heartbeat_age_seconds: float | None = None
    stale: bool = False

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def lock_info(st: SourceStatus | None, now: datetime) -> LockInfo:
    """``now`` must be database time (``db_now``)."""
    if st is None or st.running_since is None:
        return LockInfo(False)
    beat = st.lock_heartbeat_at or st.running_since
    beat_age = (now - beat).total_seconds()
    return LockInfo(True, st.lock_owner, st.running_since, beat, round((now - st.running_since).total_seconds(), 1),
                    round(beat_age, 1), beat_age > stale_after().total_seconds())


@dataclass
class ScheduleInfo:
    worker_scheduled: bool                    # a future (or just-due) scan is planned by a live worker
    next_scheduled_scan: datetime | None      # kept even when overdue, for diagnostics
    next_scan_overdue: bool
    next_scan_overdue_seconds: float | None   # seconds past the scheduled time, when overdue

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def schedule_info(st: SourceStatus | None, now: datetime) -> ScheduleInfo:
    """``now`` must be database time. The worker stores ``next_run_at`` in database time too.

    A graceful shutdown clears ``next_run_at`` (not scheduled). A hard-killed worker leaves it
    behind; once it is more than ``scan_schedule_overdue_seconds`` in the past it is OVERDUE.
    """
    nxt = st.next_run_at if st is not None else None
    if nxt is None:
        return ScheduleInfo(False, None, False, None)
    grace = get_user_config().sources.scheduler.scan_schedule_overdue_seconds
    late = (now - nxt).total_seconds()
    overdue = late > grace
    return ScheduleInfo(not overdue, nxt, overdue, round(late, 1) if overdue else None)


def _ensure_row(source: str) -> None:
    with session_scope() as s:
        if s.get(SourceStatus, source) is None:
            s.add(SourceStatus(source=source, consecutive_failures=0, health_alert_sent=False))


def acquire(source: str, owner: str | None = None) -> bool:
    """Take the lock if it is free or stale. Atomic across processes."""
    owner = owner or owner_id()
    _ensure_row(source)
    with session_scope() as s:
        now = db_now(s)
        before = lock_info(s.get(SourceStatus, source), now)
        last_beat = func.coalesce(SourceStatus.lock_heartbeat_at, SourceStatus.running_since)
        res = s.execute(update(SourceStatus).where(
            SourceStatus.source == source,
            SourceStatus.running_since.is_(None) | (last_beat < now - stale_after()),
        ).values(running_since=now, lock_heartbeat_at=now, lock_owner=owner))
        acquired = (res.rowcount or 0) == 1
    if acquired and before.locked:
        log.warning("stale_lock_reclaimed", collector=source, previous_owner=before.owner,
                    heartbeat_age_s=before.heartbeat_age_seconds, owner=owner)
    return acquired


def heartbeat(source: str, owner: str | None = None) -> bool:
    owner = owner or owner_id()
    with session_scope() as s:
        res = s.execute(update(SourceStatus).where(SourceStatus.source == source, SourceStatus.lock_owner == owner)
                        .values(lock_heartbeat_at=db_now(s)))
        return (res.rowcount or 0) == 1


def release(source: str, owner: str | None = None) -> bool:
    """Release only our own lock; never another process's valid lock."""
    owner = owner or owner_id()
    with session_scope() as s:
        res = s.execute(update(SourceStatus).where(SourceStatus.source == source, SourceStatus.lock_owner == owner)
                        .values(running_since=None, lock_heartbeat_at=None, lock_owner=None))
        released = (res.rowcount or 0) == 1
    if not released:
        log.warning("lock_release_skipped_not_owner", collector=source, owner=owner)
    return released


def recover_stale_locks() -> list[dict]:
    """Worker start-up: free abandoned locks and log each recovery. Returns what was freed."""
    me = owner_id()
    recovered: list[dict] = []
    with session_scope() as s:
        now = db_now(s)
        for st in s.scalars(select(SourceStatus).where(SourceStatus.running_since.is_not(None))).all():
            info = lock_info(st, now)
            predecessor = bool(st.lock_owner and st.lock_owner.startswith(same_host_worker_prefix())
                               and st.lock_owner != me)
            if not (info.stale or predecessor):
                continue
            reason = "stale" if info.stale else "previous worker process on this host"
            st.running_since, st.lock_heartbeat_at, st.lock_owner = None, None, None
            recovered.append({"source": st.source, "previous_owner": info.owner, "reason": reason,
                              "heartbeat_age_s": info.heartbeat_age_seconds})
            log.warning("stale_lock_recovered", collector=st.source, previous_owner=info.owner, reason=reason,
                        heartbeat_age_s=info.heartbeat_age_seconds)
    return recovered


@contextmanager
def scan_lock(source: str) -> Iterator[bool]:
    """Hold the source lock for the duration of the block, heartbeating in the background.

    Yields False (and does nothing) if another process holds a valid lock. The lock is
    released in ``finally`` whether the block completes or raises.
    """
    owner = owner_id()
    if not acquire(source, owner):
        yield False
        return
    stop = threading.Event()

    def _beat() -> None:
        while not stop.wait(heartbeat_interval()):
            try:
                heartbeat(source, owner)
            except Exception as exc:  # heartbeat problems must not kill the scan
                log.warning("lock_heartbeat_failed", collector=source, error=type(exc).__name__)

    beater = threading.Thread(target=_beat, name=f"lock-heartbeat-{source}", daemon=True)
    beater.start()
    try:
        yield True
    finally:
        stop.set()
        beater.join(timeout=5)
        release(source, owner)

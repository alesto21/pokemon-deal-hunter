"""Scan locks, graceful worker shutdown and stale-lock recovery."""

from __future__ import annotations

import socket
import threading
import time
from datetime import datetime, timedelta

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import create_engine, select, text

from app.collectors.base import CollectorResult
from app.db.base import Base
from app.db.clock import db_now
from app.db.models import CollectorRun, SourceStatus
from app.db.session import session_scope, set_engine
from app.services import lifecycle, locks, scan
from app.worker import graceful_shutdown

SRC = "cardtrader"


@pytest.fixture(autouse=True)
def _reset_lifecycle():
    lifecycle.shutdown_event.clear()
    lifecycle.set_role("cli")
    yield
    lifecycle.shutdown_event.clear()
    lifecycle.set_role("cli")


@pytest.fixture()
def file_engine(tmp_path):
    """Real per-thread connections (the in-memory StaticPool shares one connection across threads)."""
    eng = create_engine(f"sqlite:///{tmp_path / 'locks.db'}", connect_args={"check_same_thread": False,
                                                                           "timeout": 30})
    Base.metadata.create_all(eng)
    set_engine(eng)
    yield eng
    eng.dispose()


def _status() -> SourceStatus | None:
    with session_scope() as s:
        st = s.get(SourceStatus, SRC)
        if st is not None:
            s.expunge(st)
        return st


def _info() -> locks.LockInfo:
    with session_scope() as s:
        return locks.lock_info(s.get(SourceStatus, SRC), db_now(s))


def _age_lock(minutes: float) -> None:
    """Pretend the lock was acquired and last heartbeat ``minutes`` ago — in database time."""
    with session_scope() as s:
        st = s.get(SourceStatus, SRC)
        past = db_now(s) - timedelta(minutes=minutes)
        st.running_since, st.lock_heartbeat_at = past, past


def _collector(fn):
    class _C:
        name = SRC

        def collect(self, session):
            fn()
            return CollectorResult()

    return _C


# ---------------------------------------------------------------- acquire / release
def test_normal_scan_acquires_and_releases(engine, monkeypatch):
    seen = {}

    def probe():
        info = _info()
        seen.update(locked=info.locked, owner=info.owner)

    monkeypatch.setattr(scan, "collector_factories", lambda: {SRC: _collector(probe)})
    assert scan.run_collector(SRC, send_alerts=False)["ok"]
    assert seen == {"locked": True, "owner": lifecycle.owner_id()}
    st = _status()
    assert st.running_since is None and st.lock_owner is None and st.lock_heartbeat_at is None


def test_exception_during_scan_still_releases(engine, monkeypatch):
    def boom():
        raise RuntimeError("collector exploded")

    monkeypatch.setattr(scan, "collector_factories", lambda: {SRC: _collector(boom)})
    out = scan.run_collector(SRC, send_alerts=False)
    assert out["ok"] is False and "exploded" in out["error"]
    assert _info().locked is False


def test_fresh_lock_is_respected(engine):
    assert locks.acquire(SRC, "worker@a#1-x")
    assert not locks.acquire(SRC, "api@b#2-y")
    _age_lock(9)  # below the 10-minute threshold
    assert not locks.acquire(SRC, "api@b#2-y")
    assert _status().lock_owner == "worker@a#1-x"


def test_stale_lock_is_reclaimed(engine, cfg):
    assert cfg.sources.scheduler.scan_lock_stale_minutes == 10
    assert locks.acquire(SRC, "worker@a#1-x")
    _age_lock(11)
    assert _info().stale
    assert locks.acquire(SRC, "api@b#2-y")
    assert _status().lock_owner == "api@b#2-y"


def test_long_scan_with_live_heartbeat_is_not_stale(engine):
    assert locks.acquire(SRC, "worker@a#1-x")
    with session_scope() as s:
        s.get(SourceStatus, SRC).running_since = db_now(s) - timedelta(minutes=30)
    assert locks.heartbeat(SRC, "worker@a#1-x")
    info = _info()
    assert info.age_seconds > 1700 and not info.stale
    assert not locks.acquire(SRC, "api@b#2-y")


def test_one_worker_cannot_release_or_heartbeat_another_valid_lock(engine):
    assert locks.acquire(SRC, "worker@a#1-x")
    assert not locks.release(SRC, "worker@b#2-y")
    assert not locks.heartbeat(SRC, "worker@b#2-y")
    assert _status().lock_owner == "worker@a#1-x"
    assert locks.release(SRC, "worker@a#1-x")


def test_scan_lock_heartbeats_while_held(engine, monkeypatch):
    monkeypatch.setattr(locks, "heartbeat_interval", lambda: 0.05)
    with locks.scan_lock(SRC) as held:
        assert held
        first = _status().lock_heartbeat_at
        time.sleep(0.3)
        assert _status().lock_heartbeat_at > first
    assert _info().locked is False


# ---------------------------------------------------------------- recovery
def test_restart_after_interrupted_scan_recovers(engine, monkeypatch):
    # A worker on this host was killed mid-scan: its lock is fresh, but that process is gone.
    dead = f"worker@{socket.gethostname()}#1-deadbeef"
    assert locks.acquire(SRC, dead)
    lifecycle.set_role("worker")  # the restarted worker
    recovered = locks.recover_stale_locks()
    assert recovered == [{"source": SRC, "previous_owner": dead, "reason": "previous worker process on this host",
                          "heartbeat_age_s": recovered[0]["heartbeat_age_s"]}]
    monkeypatch.setattr(scan, "collector_factories", lambda: {SRC: _collector(lambda: None)})
    assert scan.run_collector(SRC, send_alerts=False)["ok"]  # resumes immediately, no dead period


def test_recovery_only_releases_stale_foreign_locks(engine):
    assert locks.acquire(SRC, "worker@other-host#1-x")  # another machine's live worker
    lifecycle.set_role("worker")
    assert locks.recover_stale_locks() == []
    assert _status().lock_owner == "worker@other-host#1-x"
    _age_lock(11)
    assert [r["reason"] for r in locks.recover_stale_locks()] == ["stale"]
    assert _info().locked is False


def test_recovery_leaves_own_lock_alone(engine):
    lifecycle.set_role("worker")
    assert locks.acquire(SRC)  # this very process
    assert locks.recover_stale_locks() == []


def test_lock_config_validation():
    from app.core.config import SchedulerConfig

    with pytest.raises(ValueError):
        SchedulerConfig(scan_lock_stale_minutes=1, scan_lock_heartbeat_seconds=45)


# ---------------------------------------------------------------- graceful shutdown
def test_no_new_scan_once_shutdown_has_begun(engine, monkeypatch):
    ran = []
    monkeypatch.setattr(scan, "collector_factories", lambda: {SRC: _collector(lambda: ran.append(1))})
    lifecycle.shutdown_event.set()
    assert scan.run_collector(SRC, send_alerts=False) == {"source": SRC, "skipped": "shutting down"}
    assert ran == [] and (_status() is None or not _info().locked)
    assert scan.reevaluate_manual_listings() == 0


def test_graceful_shutdown_waits_for_running_scan(file_engine, monkeypatch):
    started, later_job_ran = threading.Event(), threading.Event()

    def slow():
        started.set()
        time.sleep(1.0)

    monkeypatch.setattr(scan, "collector_factories", lambda: {SRC: _collector(slow)})
    sched = BackgroundScheduler()
    sched.add_job(scan.run_collector, args=[SRC], kwargs={"send_alerts": False}, id="cardtrader",
                  next_run_time=datetime.now().astimezone())
    # a job due while shutdown is waiting must NOT start
    sched.add_job(later_job_ran.set, id="later", next_run_time=datetime.now().astimezone() + timedelta(seconds=0.4))
    sched.start()
    assert started.wait(5), "scan did not start"
    assert _info().locked

    t0 = time.monotonic()
    graceful_shutdown(sched, reason="SIGTERM")
    waited = time.monotonic() - t0

    assert waited >= 0.5  # shutdown blocked until the scan finished
    assert not later_job_ran.is_set()
    assert not sched.running
    assert _info().locked is False  # released by the finishing scan
    with session_scope() as s:
        run = s.scalars(select(CollectorRun)).one()
        assert run.success  # completed, not abandoned
    graceful_shutdown(sched, reason="SIGINT")  # second signal is a no-op


# ---------------------------------------------------------------- database clock
def test_stale_detection_uses_database_time(engine):
    assert locks.acquire(SRC, "worker@a#1-x")
    with session_scope() as s:  # set the heartbeat 11 min in the past using the DB's own clock
        s.execute(text("UPDATE source_status SET lock_heartbeat_at = datetime('now', '-11 minutes'), "
                       "running_since = datetime('now', '-11 minutes') WHERE source = :s"), {"s": SRC})
    assert _info().stale
    assert locks.acquire(SRC, "api@b#2-y")


@pytest.mark.parametrize("skew", [timedelta(hours=3), -timedelta(hours=3)])
def test_app_clock_skew_does_not_affect_lock_decisions(engine, monkeypatch, skew):
    """A process whose clock is hours off must neither steal a fresh lock nor keep a stale one."""
    import app.db.base as base

    real = base.utcnow
    monkeypatch.setattr(base, "utcnow", lambda: real() + skew)
    assert locks.acquire(SRC, "worker@a#1-x")
    assert not _info().stale
    assert not locks.acquire(SRC, "api@b#2-y")  # fresh lock respected despite skew
    _age_lock(11)
    assert _info().stale
    assert locks.acquire(SRC, "api@b#2-y")      # stale lock reclaimed despite skew


def test_heartbeat_prevents_reclaim_in_database_time(engine):
    assert locks.acquire(SRC, "worker@a#1-x")
    _age_lock(11)
    assert locks.heartbeat(SRC, "worker@a#1-x")  # the owner is alive after all
    assert not _info().stale
    assert not locks.acquire(SRC, "api@b#2-y")


def test_next_run_is_stored_in_database_time(engine):
    from app.worker import record_next_runs

    sched = BackgroundScheduler()
    sched.add_job(lambda: None, "interval", minutes=30, id=SRC,
                  next_run_time=datetime.now().astimezone() + timedelta(minutes=5))
    sched.start(paused=True)
    try:
        record_next_runs(sched)
    finally:
        sched.shutdown(wait=False)
    with session_scope() as s:
        delta = (s.get(SourceStatus, SRC).next_run_at - db_now(s)).total_seconds()
    assert 280 < delta <= 300


# ---------------------------------------------------------------- schedule health / overdue
def _sched(offset_seconds: float | None) -> locks.ScheduleInfo:
    with session_scope() as s:
        now = db_now(s)
        st = SourceStatus(source=SRC, next_run_at=None if offset_seconds is None
                          else now + timedelta(seconds=offset_seconds))
        return locks.schedule_info(st, now)


@pytest.mark.parametrize("offset,scheduled,overdue", [
    (300, True, False),     # future next scan
    (-60, True, False),     # slightly past, inside the 120 s grace (job may just be running)
    (-121, False, True),    # past the grace
    (-3600, False, True),   # long dead
])
def test_schedule_overdue_detection(engine, offset, scheduled, overdue):
    info = _sched(offset)
    assert (info.worker_scheduled, info.next_scan_overdue) == (scheduled, overdue)
    assert info.next_scheduled_scan is not None  # timestamp preserved for diagnostics
    if overdue:
        assert info.next_scan_overdue_seconds == pytest.approx(-offset, abs=2)
    else:
        assert info.next_scan_overdue_seconds is None


def test_no_timestamp_is_not_overdue(engine):
    info = _sched(None)
    assert info == locks.ScheduleInfo(False, None, False, None)


def test_graceful_shutdown_clears_schedule_but_hard_kill_goes_overdue(file_engine):
    from app.worker import record_next_runs

    sched = BackgroundScheduler()
    sched.add_job(lambda: None, "interval", minutes=30, id=SRC,
                  next_run_time=datetime.now().astimezone() + timedelta(minutes=1))
    sched.start()
    record_next_runs(sched)
    with session_scope() as s:
        assert locks.schedule_info(s.get(SourceStatus, SRC), db_now(s)).worker_scheduled

    # hard kill: nothing clears next_run_at; time passes beyond schedule + grace
    with session_scope() as s:
        st = s.get(SourceStatus, SRC)
        st.next_run_at = db_now(s) - timedelta(minutes=5)
    with session_scope() as s:
        info = locks.schedule_info(s.get(SourceStatus, SRC), db_now(s))
        assert info.next_scan_overdue and not info.worker_scheduled

    # a restarted worker records a fresh schedule → overdue clears
    record_next_runs(sched)
    with session_scope() as s:
        assert not locks.schedule_info(s.get(SourceStatus, SRC), db_now(s)).next_scan_overdue

    # graceful shutdown clears the scheduled state entirely
    graceful_shutdown(sched, reason="SIGTERM")
    with session_scope() as s:
        info = locks.schedule_info(s.get(SourceStatus, SRC), db_now(s))
        assert info == locks.ScheduleInfo(False, None, False, None)

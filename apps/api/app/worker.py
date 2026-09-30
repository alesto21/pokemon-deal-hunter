"""Scheduler process (APScheduler). Run with: python -m app.worker"""

from __future__ import annotations

import signal
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
from apscheduler.schedulers.base import BaseScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings, get_user_config
from app.core.logging import configure_logging, get_logger
from app.services.lifecycle import set_role, shutdown_event
from app.services.locks import recover_stale_locks
from app.services.maintenance import refresh_fx, run_maintenance, send_watch_digest, snapshot_portfolio
from app.services.scan import reevaluate_manual_listings, run_collector

log = get_logger("worker")
HEARTBEAT = Path("/tmp/worker-heartbeat")
SOURCE_JOBS = ("cardtrader", "stores")  # scheduler job id == source name


def _safe(name: str, fn, *args) -> None:
    try:
        fn(*args)
    except Exception as exc:  # a failing job must never kill the scheduler
        log.error("job_failed", job=name, error=f"{type(exc).__name__}: {exc}")


def heartbeat(scheduler: BaseScheduler | None = None) -> None:
    HEARTBEAT.write_text(str(int(time.time())))
    if scheduler is not None:
        record_next_runs(scheduler)


def record_next_runs(scheduler: BaseScheduler | None) -> None:
    """Store each source's next scheduled scan so the API can show it. None = not scheduled.

    Stored in *database* time (DB now + time until the job fires), so overdue detection does not
    depend on this process's clock agreeing with the database.
    """
    from app.db.clock import db_now
    from app.db.models import SourceStatus
    from app.db.session import session_scope

    with session_scope() as s:
        now_db, now_local = db_now(s), datetime.now(UTC)
        for source in SOURCE_JOBS:
            job = scheduler.get_job(source) if scheduler is not None else None
            nxt = now_db + (job.next_run_time - now_local) if job and job.next_run_time else None
            st = s.get(SourceStatus, source)
            if st is None:
                if nxt is None:
                    continue
                st = SourceStatus(source=source, consecutive_failures=0, health_alert_sent=False)
                s.add(st)
            st.next_run_at = nxt


def graceful_shutdown(scheduler: BaseScheduler, reason: str = "signal") -> None:
    """Stop taking new jobs, let the running scan finish (it releases its own lock), then stop.

    Order matters: the shutdown flag makes ``run_collector`` refuse new scans even if a job
    was already dispatched; ``pause`` stops the scheduler from dispatching more; ``shutdown
    (wait=True)`` joins the executor, i.e. waits for the running job to complete.
    """
    if shutdown_event.is_set():
        log.info("shutdown_already_in_progress", reason=reason)
        return
    shutdown_event.set()
    log.info("scheduler_stopping", reason=reason, action="no new jobs; waiting for any running job")
    if scheduler.running:
        scheduler.pause()
    _safe("record_next_runs", record_next_runs, None)  # health shows "no scan scheduled"
    if scheduler.running:
        scheduler.shutdown(wait=True)
    log.info("scheduler_stopped", reason=reason)


def scan_cardtrader() -> None:
    _safe("cardtrader", run_collector, "cardtrader")
    if not shutdown_event.is_set():
        _safe("reevaluate_manual", reevaluate_manual_listings)


def build_scheduler() -> BlockingScheduler:
    cfg = get_user_config()
    src, sched = cfg.sources, cfg.sources.scheduler
    scheduler = BlockingScheduler(timezone="Europe/Oslo", job_defaults={"coalesce": True, "max_instances": 1,
                                                                        "misfire_grace_time": 600})
    scheduler.add_job(heartbeat, IntervalTrigger(seconds=60), args=[scheduler], id="heartbeat",
                      next_run_time=_now(delay=1))
    scheduler.add_job(lambda: _safe("fx", refresh_fx), CronTrigger(hour=sched.fx_refresh_hour, minute=5), id="fx")
    if src.cardtrader.enabled:
        scheduler.add_job(scan_cardtrader, IntervalTrigger(minutes=src.cardtrader.interval_minutes),
                          id="cardtrader", next_run_time=_now(delay=20))
    if src.stores.enabled:
        scheduler.add_job(lambda: _safe("stores", run_collector, "stores"),
                          IntervalTrigger(minutes=src.stores.interval_minutes), id="stores",
                          next_run_time=_now(delay=90))
    scheduler.add_job(lambda: _safe("maintenance", run_maintenance),
                      CronTrigger(hour=sched.maintenance_hour, minute=15), id="maintenance")
    scheduler.add_job(lambda: _safe("portfolio_snapshot", snapshot_portfolio),
                      CronTrigger(hour=sched.portfolio_snapshot_hour, minute=0), id="portfolio_snapshot")
    # Keep "next scheduled scan" current right after each scan, not only on the minute heartbeat.
    scheduler.add_listener(
        lambda event: _safe("record_next_runs", record_next_runs, scheduler)
        if event.job_id in SOURCE_JOBS and not shutdown_event.is_set() else None,
        EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED)
    if cfg.alerts.watch_digest.enabled:
        scheduler.add_job(lambda: _safe("watch_digest", send_watch_digest),
                          CronTrigger(hour=cfg.alerts.watch_digest.hour, minute=0), id="watch_digest")
    return scheduler


def _now(delay: int = 0) -> datetime:
    return datetime.now().astimezone() + timedelta(seconds=delay)


def main() -> None:
    set_role("worker")
    s = get_settings()
    configure_logging(s.log_level, s.log_json)
    recovered = recover_stale_locks()
    log.info("startup_lock_recovery", recovered=len(recovered), details=recovered)
    _safe("fx", refresh_fx)
    _safe("portfolio_snapshot", snapshot_portfolio)
    scheduler = build_scheduler()
    jobs = [j.id for j in scheduler.get_jobs()]
    log.info("scheduler_started", jobs=jobs, cardtrader_mode="mock" if s.cardtrader_is_mock else "live",
             telegram_mode="dry-run" if s.telegram_is_dry_run else "live")

    def _stop(signum, _frame):
        graceful_shutdown(scheduler, reason=signal.Signals(signum).name)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    scheduler.start()


if __name__ == "__main__":
    main()

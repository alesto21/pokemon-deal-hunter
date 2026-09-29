"""Scheduler process (APScheduler). Run with: python -m app.worker"""

from __future__ import annotations

import signal
import time
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings, get_user_config
from app.core.logging import configure_logging, get_logger
from app.services.maintenance import refresh_fx, run_maintenance, send_watch_digest, snapshot_portfolio
from app.services.scan import reevaluate_manual_listings, run_collector

log = get_logger("worker")
HEARTBEAT = Path("/tmp/worker-heartbeat")


def _safe(name: str, fn, *args) -> None:
    try:
        fn(*args)
    except Exception as exc:  # a failing job must never kill the scheduler
        log.error("job_failed", job=name, error=f"{type(exc).__name__}: {exc}")


def heartbeat() -> None:
    HEARTBEAT.write_text(str(int(time.time())))


def scan_cardtrader() -> None:
    _safe("cardtrader", run_collector, "cardtrader")
    _safe("reevaluate_manual", reevaluate_manual_listings)


def build_scheduler() -> BlockingScheduler:
    cfg = get_user_config()
    src, sched = cfg.sources, cfg.sources.scheduler
    scheduler = BlockingScheduler(timezone="Europe/Oslo", job_defaults={"coalesce": True, "max_instances": 1,
                                                                        "misfire_grace_time": 600})
    scheduler.add_job(heartbeat, IntervalTrigger(seconds=60), id="heartbeat", next_run_time=_now())
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
    if cfg.alerts.watch_digest.enabled:
        scheduler.add_job(lambda: _safe("watch_digest", send_watch_digest),
                          CronTrigger(hour=cfg.alerts.watch_digest.hour, minute=0), id="watch_digest")
    return scheduler


def _now(delay: int = 0):
    from datetime import datetime, timedelta

    return datetime.now().astimezone() + timedelta(seconds=delay)


def main() -> None:
    s = get_settings()
    configure_logging(s.log_level, s.log_json)
    _safe("fx", refresh_fx)
    _safe("portfolio_snapshot", snapshot_portfolio)
    scheduler = build_scheduler()
    jobs = [j.id for j in scheduler.get_jobs()]
    log.info("scheduler_started", jobs=jobs, cardtrader_mode="mock" if s.cardtrader_is_mock else "live",
             telegram_mode="dry-run" if s.telegram_is_dry_run else "live")

    def _stop(*_):
        log.info("scheduler_stopping")
        scheduler.shutdown(wait=False)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    scheduler.start()


if __name__ == "__main__":
    main()

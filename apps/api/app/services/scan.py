"""Collector orchestration: locking, run bookkeeping, health tracking, health alerts."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.base import Collector
from app.core.config import get_user_config
from app.core.logging import get_logger, redact_text
from app.db.base import utcnow
from app.db.models import Alert, CollectorRun, Listing, ListingStatus, SourceStatus
from app.db.session import session_scope
from app.notifications.telegram import TelegramNotifier
from app.pricing.history import aggregate_day
from app.services.evaluation import evaluate_listing, needs_evaluation
from app.services.lifecycle import shutting_down
from app.services.locks import scan_lock

log = get_logger(__name__)


def collector_factories() -> dict[str, Callable[[], Collector]]:
    from app.collectors.cardtrader import CardTraderCollector
    from app.collectors.stores import StoreCollector

    return {"cardtrader": CardTraderCollector, "stores": StoreCollector}


def _status(session: Session, source: str) -> SourceStatus:
    st = session.get(SourceStatus, source)
    if st is None:
        st = SourceStatus(source=source, consecutive_failures=0, health_alert_sent=False)
        session.add(st)
        session.flush()
    return st


def run_collector(source: str, send_alerts: bool = True, notifier: TelegramNotifier | None = None) -> dict:
    """Run one collector under its scan lock. The lock is always released (see ``locks.scan_lock``)."""
    factories = collector_factories()
    if source not in factories:
        raise ValueError(f"Unknown source {source}; choose from {', '.join(factories)}")
    if shutting_down():
        log.info("collector_skipped_shutdown", collector=source, action="skip")
        return {"source": source, "skipped": "shutting down"}
    with scan_lock(source) as acquired:
        if not acquired:
            log.warning("collector_already_running", collector=source, action="skip")
            return {"source": source, "skipped": "already running"}
        return _run_locked(source, factories[source], send_alerts, notifier)


def _run_locked(source: str, factory: Callable[[], Collector], send_alerts: bool,
                notifier: TelegramNotifier | None) -> dict:
    started = utcnow()
    t0 = time.monotonic()
    summary: dict = {"source": source}
    try:
        with session_scope() as s:
            collector = factory()
            result = collector.collect(s)
            s.flush()
            evaluated = deals = alerts = 0
            for lid in dict.fromkeys(result.listing_ids):
                listing = s.get(Listing, lid)
                if listing is None or not needs_evaluation(s, listing):
                    continue
                ev, _res, decision = evaluate_listing(s, listing, send_alerts, notifier)
                evaluated += 1
                deals += ev.alert_level in ("GOOD", "STRONG_BUY", "STEAL")
                alerts += bool(decision and decision.notify)
            _mark_gone(s, source, started)
            aggregate_day(s, date.today())
            duration = int((time.monotonic() - t0) * 1000)
            s.add(CollectorRun(source=source, started_at=started, finished_at=utcnow(), success=True,
                               duration_ms=duration, items_fetched=result.fetched, items_matched=result.matched,
                               listings_evaluated=evaluated, deals_found=deals, alerts_sent=alerts,
                               error="; ".join(result.notes) or None))
            st = _status(s, source)
            recovered = st.health_alert_sent
            st.last_success, st.consecutive_failures, st.health_alert_sent = utcnow(), 0, False
            summary.update(ok=True, fetched=result.fetched, matched=result.matched, evaluated=evaluated,
                           deals=deals, alerts=alerts, duration_ms=duration, notes=result.notes)
        if recovered:
            _health_message(f"✅ Source <b>{source}</b> recovered.", source, notifier)
        log.info("collector_run_ok", collector=source, **{k: v for k, v in summary.items() if k != "source"})
    except Exception as exc:
        err = redact_text(f"{type(exc).__name__}: {exc}")[:1000]
        log.error("collector_run_failed", collector=source, error=err)
        summary.update(ok=False, error=err)
        _record_failure(source, started, int((time.monotonic() - t0) * 1000), err, notifier)
    return summary


def _record_failure(source: str, started, duration: int, err: str, notifier: TelegramNotifier | None) -> None:
    threshold = get_user_config().alerts.source_health.get("failures_before_alert", 3)
    send = False
    with session_scope() as s:
        s.add(CollectorRun(source=source, started_at=started, finished_at=utcnow(), success=False,
                           duration_ms=duration, error=err))
        st = _status(s, source)
        st.last_failure, st.last_error = utcnow(), err
        st.consecutive_failures = (st.consecutive_failures or 0) + 1
        if st.consecutive_failures >= threshold and not st.health_alert_sent:
            st.health_alert_sent = True
            send = True
    if send:
        from html import escape

        _health_message(f"⚠️ Source <b>{source}</b> is unhealthy ({threshold}+ consecutive failures).\n"
                        f"<code>{escape(err[:300])}</code>", source, notifier)


def _health_message(text: str, source: str, notifier: TelegramNotifier | None) -> None:
    sent = (notifier or TelegramNotifier()).send(text)
    with session_scope() as s:
        s.add(Alert(kind="health", severity="HEALTH", message=text, dry_run=sent.dry_run,
                    telegram_message_id=sent.message_id))


def _mark_gone(session: Session, source: str, run_started) -> None:
    """Automated sources: listings not seen in this run are gone."""
    prefix_filter = Listing.source.like("store:%") if source == "stores" else Listing.source == source
    for listing in session.scalars(select(Listing).where(
            prefix_filter, Listing.status == ListingStatus.ACTIVE, Listing.last_seen < run_started)).all():
        listing.status = ListingStatus.GONE


def reevaluate_manual_listings(send_alerts: bool = True, notifier: TelegramNotifier | None = None) -> int:
    """Re-score active FINN/manual listings against fresh fair values (no network access)."""
    if shutting_down():
        return 0
    n = 0
    with session_scope() as s:
        for listing in s.scalars(select(Listing).where(
                Listing.status == ListingStatus.ACTIVE, Listing.source.in_(["finn", "manual"]))).all():
            if needs_evaluation(s, listing, max_age_hours=6):
                evaluate_listing(s, listing, send_alerts, notifier)
                n += 1
    return n

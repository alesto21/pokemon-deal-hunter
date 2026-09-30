"""Daily housekeeping: aggregates, retention, stale listings, FX, portfolio snapshot, digest."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, select

from app.core.config import get_user_config
from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.models import Alert, DealEvaluation, Listing, ListingStatus
from app.db.session import session_scope
from app.notifications.telegram import TelegramNotifier
from app.portfolio.service import take_portfolio_snapshot, value_holdings
from app.pricing.fx import refresh_rates
from app.pricing.history import apply_retention
from app.services.market import fair_value_nok

log = get_logger(__name__)


def run_maintenance() -> dict:
    cfg = get_user_config().sources.retention
    with session_scope() as s:
        out = apply_retention(s, cfg.raw_snapshot_days, cfg.collector_run_days)
        cutoff = utcnow() - timedelta(days=cfg.listing_gone_after_days)
        stale = s.scalars(select(Listing).where(Listing.status == ListingStatus.ACTIVE,
                                                Listing.last_seen < cutoff)).all()
        for listing in stale:
            listing.status = ListingStatus.GONE
        alerted = select(Alert.deal_evaluation_id).where(Alert.deal_evaluation_id.is_not(None))
        res = s.execute(delete(DealEvaluation).where(
            DealEvaluation.timestamp < utcnow() - timedelta(days=cfg.evaluation_days),
            DealEvaluation.id.not_in(alerted)))
        out.update(listings_marked_gone=len(stale), evaluations_deleted=res.rowcount or 0)
    log.info("maintenance_done", **out)
    return out


def refresh_fx() -> None:
    with session_scope() as s:
        refresh_rates(s)


def snapshot_portfolio() -> None:
    with session_scope() as s:
        take_portfolio_snapshot(s, value_holdings(s, lambda t, i: fair_value_nok(s, t, i)))


def send_watch_digest(notifier: TelegramNotifier | None = None) -> int:
    """Optional daily digest of WATCH items (disabled by default in alerts.yaml)."""
    since = utcnow() - timedelta(days=1)
    with session_scope() as s:
        evs = s.scalars(select(DealEvaluation).where(DealEvaluation.timestamp >= since,
                                                     DealEvaluation.alert_level == "WATCH")
                        .order_by(DealEvaluation.total_score.desc()).limit(15)).all()
        if not evs:
            return 0
        from html import escape
        lines = [f"👁 <b>WATCH digest</b> — {datetime.now():%d.%m}"]
        seen = set()
        for ev in evs:
            if ev.listing_id in seen:
                continue
            seen.add(ev.listing_id)
            lines.append(f"• {escape(ev.listing.title[:60])} — {ev.price_nok:.0f} NOK "
                         f"(score {ev.total_score:.0f}, {(ev.discount_pct or 0):.0%})")
        text = "\n".join(lines)
        sent = (notifier or TelegramNotifier()).send(text)
        s.add(Alert(kind="digest", severity="WATCH", message=text, dry_run=sent.dry_run,
                    telegram_message_id=sent.message_id))
        return len(seen)

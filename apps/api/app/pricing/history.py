"""Price history: raw snapshots, daily aggregates, rolling windows, retention."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import CollectorRun, PriceDaily, PriceSnapshot
from app.pricing.stats import PriceStats


@dataclass
class HistoryStats:
    median_7d: float | None = None
    median_30d: float | None = None
    median_90d: float | None = None
    median_all: float | None = None
    days_30d: int = 0
    trend_30d: float | None = None     # relative change first→last week of the window
    volatility_30d: float | None = None  # stdev of daily log returns
    avg_listing_count_30d: float | None = None


def record_snapshot(session: Session, entity_type: str, entity_id: int, source: str, stats: PriceStats,
                    ts: datetime | None = None) -> PriceSnapshot | None:
    if stats.count == 0:
        return None
    snap = PriceSnapshot(
        entity_type=entity_type, entity_id=entity_id, source=source, timestamp=ts or utcnow(),
        low_price=stats.low, median_price=stats.median, trimmed_median=stats.trimmed_median,
        cheapest5_median=stats.cheapest5_median, listing_count=stats.count,
        seller_count=stats.seller_count, dispersion=stats.dispersion, currency="NOK",
    )
    session.add(snap)
    return snap


def latest_snapshot(session: Session, entity_type: str, entity_id: int, max_age_hours: float = 72
                    ) -> PriceSnapshot | None:
    since = utcnow() - timedelta(hours=max_age_hours)
    return session.scalar(
        select(PriceSnapshot)
        .where(PriceSnapshot.entity_type == entity_type, PriceSnapshot.entity_id == entity_id,
               PriceSnapshot.timestamp >= since)
        .order_by(PriceSnapshot.timestamp.desc())
        .limit(1)
    )


def aggregate_day(session: Session, day: date, entities: set[tuple[str, int]] | None = None) -> int:
    """(Re)build PriceDaily rows for ``day`` from raw snapshots. Idempotent.

    ``entities`` limits the rebuild to specific (entity_type, entity_id) pairs.
    """
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    q = select(PriceSnapshot).where(PriceSnapshot.timestamp >= start, PriceSnapshot.timestamp < end)
    if entities is not None:
        if not entities:
            return 0
        q = q.where(PriceSnapshot.entity_id.in_({e[1] for e in entities}))
    snaps = [s for s in session.scalars(q).all()
             if entities is None or (s.entity_type, s.entity_id) in entities]
    groups: dict[tuple[str, int, str], list[PriceSnapshot]] = {}
    for s in snaps:
        groups.setdefault((s.entity_type, s.entity_id, s.source), []).append(s)
    for (etype, eid, source), rows in groups.items():
        def med(attr: str, rows=rows) -> float | None:
            vals = [getattr(r, attr) for r in rows if getattr(r, attr) is not None]
            return round(statistics.median(vals), 2) if vals else None

        existing = session.scalar(select(PriceDaily).where(
            PriceDaily.entity_type == etype, PriceDaily.entity_id == eid, PriceDaily.source == source,
            PriceDaily.day == day))
        row = existing or PriceDaily(entity_type=etype, entity_id=eid, source=source, day=day)
        row.low_price = min((r.low_price for r in rows if r.low_price is not None), default=None)
        row.median_price = med("median_price")
        row.trimmed_median = med("trimmed_median")
        row.listing_count = med("listing_count")
        row.samples = len(rows)
        if not existing:
            session.add(row)
    session.flush()
    return len(groups)


def daily_series(session: Session, entity_type: str, entity_id: int, days: int | None = 90) -> list[PriceDaily]:
    q = select(PriceDaily).where(PriceDaily.entity_type == entity_type, PriceDaily.entity_id == entity_id)
    if days:
        q = q.where(PriceDaily.day >= date.today() - timedelta(days=days))
    return list(session.scalars(q.order_by(PriceDaily.day)).all())


def _window_median(series: list[PriceDaily], days: int) -> tuple[float | None, int]:
    cutoff = date.today() - timedelta(days=days)
    vals = [r.trimmed_median or r.median_price for r in series if r.day >= cutoff]
    vals = [v for v in vals if v]
    return (round(statistics.median(vals), 2) if vals else None), len(vals)


def compute_history_stats(series: list[PriceDaily]) -> HistoryStats:
    """Rolling medians, trend and volatility from a daily series (oldest first)."""
    h = HistoryStats()
    if not series:
        return h
    h.median_7d, _ = _window_median(series, 7)
    h.median_30d, h.days_30d = _window_median(series, 30)
    h.median_90d, _ = _window_median(series, 90)
    all_vals = [r.trimmed_median or r.median_price for r in series if (r.trimmed_median or r.median_price)]
    h.median_all = round(statistics.median(all_vals), 2) if all_vals else None
    cutoff = date.today() - timedelta(days=30)
    window = [r for r in series if r.day >= cutoff and (r.trimmed_median or r.median_price)]
    prices = [float(r.trimmed_median or r.median_price) for r in window]  # type: ignore[arg-type]
    if len(prices) >= 5:
        k = max(1, len(prices) // 4)
        start, end = statistics.median(prices[:k]), statistics.median(prices[-k:])
        h.trend_30d = round((end - start) / start, 4) if start else None
        rets = [math.log(b / a) for a, b in zip(prices, prices[1:], strict=False) if a > 0 and b > 0]
        h.volatility_30d = round(statistics.pstdev(rets), 4) if len(rets) >= 2 else None
    counts = [r.listing_count for r in window if r.listing_count is not None]
    h.avg_listing_count_30d = round(statistics.mean(counts), 1) if counts else None
    return h


def apply_retention(session: Session, raw_days: int, run_days: int) -> dict[str, int]:
    """Aggregate everything first, then drop raw snapshots / collector runs past retention."""
    oldest = session.scalar(select(func.min(PriceSnapshot.timestamp)))
    if oldest:
        d = oldest.date()
        while d <= date.today():
            aggregate_day(session, d)
            d += timedelta(days=1)
    cutoff = utcnow() - timedelta(days=raw_days)
    snaps = session.execute(delete(PriceSnapshot).where(PriceSnapshot.timestamp < cutoff)).rowcount
    runs = session.execute(
        delete(CollectorRun).where(CollectorRun.started_at < utcnow() - timedelta(days=run_days))
    ).rowcount
    return {"snapshots_deleted": snaps or 0, "runs_deleted": runs or 0}

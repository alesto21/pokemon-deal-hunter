"""Market view of an entity: current stats + history → fair value."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_user_config
from app.pricing.fair_value import CurrentMarket, FairValue, estimate_fair_value
from app.pricing.history import HistoryStats, compute_history_stats, daily_series, latest_snapshot


@dataclass
class MarketView:
    current: CurrentMarket
    history: HistoryStats
    fair_value: FairValue


def market_view(session: Session, entity_type: str, entity_id: int, identity_confidence: float = 1.0) -> MarketView:
    fv_cfg = get_user_config().scoring.fair_value
    snap = latest_snapshot(session, entity_type, entity_id)
    current = CurrentMarket(
        low=snap.low_price, median=snap.median_price, trimmed_median=snap.trimmed_median,
        cheapest5_median=snap.cheapest5_median, listing_count=snap.listing_count, dispersion=snap.dispersion,
        cheapest3_median=snap.cheapest3_median, cheapest10_median=snap.cheapest10_median,
        has_expensive_tail=bool(snap.has_expensive_tail),
        low_is_outlier=bool(snap.low_price and snap.cheapest5_median and snap.listing_count >= 3
                            and snap.low_price < snap.cheapest5_median * fv_cfg.low_outlier_ratio),
    ) if snap else CurrentMarket()
    history = compute_history_stats(daily_series(session, entity_type, entity_id, 90))
    fv = estimate_fair_value(current, history, fv_cfg, identity_confidence)
    return MarketView(current, history, fv)


def fair_value_nok(session: Session, entity_type: str, entity_id: int) -> float | None:
    return market_view(session, entity_type, entity_id).fair_value.fair_value_nok

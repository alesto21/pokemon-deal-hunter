"""Conservative fair-value estimator.

Never simply "the cheapest listing": we blend a trimmed current median with the
median of the cheapest five asks, then blend with our own 30-day history, and we
lower confidence when data is thin, dispersed, volatile or identity is uncertain.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import FairValueConfig
from app.pricing.history import HistoryStats


@dataclass
class CurrentMarket:
    low: float | None = None
    median: float | None = None
    trimmed_median: float | None = None
    cheapest5_median: float | None = None
    listing_count: int = 0
    dispersion: float | None = None


@dataclass
class FairValue:
    fair_value_nok: float | None
    fair_value_low: float | None
    fair_value_high: float | None
    confidence: float
    explanation: list[str] = field(default_factory=list)


def _count_factor(n: int) -> float:
    if n >= 10:
        return 1.0
    if n >= 5:
        return 0.85
    if n >= 3:
        return 0.7
    if n >= 1:
        return 0.45
    return 0.0


def estimate_fair_value(
    current: CurrentMarket,
    history: HistoryStats,
    cfg: FairValueConfig,
    identity_confidence: float = 1.0,
) -> FairValue:
    notes: list[str] = []
    conf = 1.0
    current_value: float | None = None

    n = current.listing_count
    if n >= cfg.min_listings_for_current and current.trimmed_median and current.cheapest5_median:
        w = cfg.current_blend
        total_w = w.get("trimmed_median", 0.6) + w.get("cheapest5_median", 0.4)
        current_value = (current.trimmed_median * w.get("trimmed_median", 0.6)
                         + current.cheapest5_median * w.get("cheapest5_median", 0.4)) / total_w
        notes.append(f"current: blend of trimmed median {current.trimmed_median:.0f} and "
                     f"cheapest-5 median {current.cheapest5_median:.0f} over {n} listings")
    elif n > 0 and (current.cheapest5_median or current.median):
        current_value = current.cheapest5_median or current.median
        notes.append(f"current: only {n} listing(s) — using their median {current_value:.0f}")
    conf *= _count_factor(n) if current_value else 1.0

    hist = history.median_30d if history.days_30d >= cfg.min_history_days else None
    if current_value and hist:
        fv = current_value * (1 - cfg.history_weight) + hist * cfg.history_weight
        notes.append(f"blended with own 30d median {hist:.0f} ({history.days_30d} days, "
                     f"weight {cfg.history_weight:.0%})")
    elif current_value:
        fv = current_value
        conf *= 0.9
        notes.append("no sufficient own history yet")
    elif hist:
        fv = hist
        conf *= 0.6
        notes.append(f"no current listings — using own 30d median {hist:.0f} (stale)")
    elif history.median_90d:
        fv = history.median_90d
        conf *= 0.4
        notes.append(f"only 90d history available ({history.median_90d:.0f})")
    else:
        return FairValue(None, None, None, 0.0, ["no market data"])

    # Conservative: when the market is falling, lean to the lower of current vs history.
    if history.trend_30d is not None and history.trend_30d < -0.05 and current_value and hist:
        fv = min(fv, current_value)
        notes.append(f"falling market ({history.trend_30d:+.1%}) — using lower current value")

    spread = 0.08
    if current.dispersion is not None and current.dispersion > cfg.high_dispersion:
        conf *= 0.75
        spread += 0.1
        notes.append(f"high price dispersion ({current.dispersion:.2f})")
    if history.volatility_30d is not None and history.volatility_30d > cfg.high_volatility:
        conf *= 0.8
        spread += 0.07
        notes.append(f"volatile prices (σ={history.volatility_30d:.2f})")
    if identity_confidence < 1.0:
        conf *= identity_confidence
        if identity_confidence < 0.9:
            notes.append(f"identity confidence only {identity_confidence:.2f}")
    spread += (1 - conf) * 0.15

    fv = round(fv, 2)
    return FairValue(
        fair_value_nok=fv,
        fair_value_low=round(fv * (1 - spread), 2),
        fair_value_high=round(fv * (1 + spread), 2),
        confidence=round(max(0.0, min(1.0, conf)), 3),
        explanation=notes,
    )

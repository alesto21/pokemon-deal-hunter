"""Conservative fair-value estimator.

Fair value is what the card can realistically be *bought* for, not what sellers ask on
average. For liquid singles the executable market dominates:

    fair = 0.60 × cheapest-5 median + 0.25 × cheapest-10 median + 0.15 × own 30d median

(weights renormalised over the parts that exist). The broad and trimmed medians are only
used to detect an expensive tail of stale asks and to explain the result. They never set
the price. A single cheap listing cannot define fair value either: it is at most one of the
five values in the cheapest-5 median.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import FairValueConfig
from app.pricing.history import HistoryStats

# Bump whenever the valuation logic changes: stored evaluations from an older model are
# re-evaluated on the next scan instead of lingering on the dashboard.
FAIR_VALUE_MODEL_VERSION = "executable-v3"


@dataclass
class CurrentMarket:
    low: float | None = None
    median: float | None = None
    trimmed_median: float | None = None
    cheapest5_median: float | None = None
    listing_count: int = 0
    dispersion: float | None = None
    cheapest3_median: float | None = None
    cheapest10_median: float | None = None
    has_expensive_tail: bool = False
    low_is_outlier: bool = False


@dataclass
class FairValue:
    fair_value_nok: float | None
    fair_value_low: float | None
    fair_value_high: float | None
    confidence: float
    explanation: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


def _thin_market_factor(n: int) -> float:
    return {0: 0.0, 1: 0.3, 2: 0.4, 3: 0.55, 4: 0.6}.get(n, 1.0)


def _blend(parts: list[tuple[str, float | None, float]]) -> tuple[float | None, list[str]]:
    """Weighted mean over the parts whose value exists, weights renormalised."""
    usable = [(name, v, w) for name, v, w in parts if v and w > 0]
    total_w = sum(w for _, _, w in usable)
    if not usable or total_w <= 0:
        return None, []
    value = sum(v * w for _, v, w in usable) / total_w
    return value, [f"{name} {v:.0f} × {w / total_w:.0%}" for name, v, w in usable]


def estimate_fair_value(
    current: CurrentMarket,
    history: HistoryStats,
    cfg: FairValueConfig,
    identity_confidence: float = 1.0,
) -> FairValue:
    notes: list[str] = []
    flags: list[str] = []
    conf = 1.0
    n = current.listing_count
    hist = history.median_30d if history.days_30d >= cfg.min_history_days else None
    w = cfg.executable_weights

    if n >= cfg.min_listings_for_executable and current.cheapest5_median:
        fv, parts = _blend([("cheapest-5 median", current.cheapest5_median, w.get("cheapest5", 0.60)),
                            ("cheapest-10 median", current.cheapest10_median, w.get("cheapest10", 0.25)),
                            ("own 30d median", hist, w.get("history30", 0.15))])
        notes.append(f"executable market over {n} valid listings: " + ", ".join(parts))
        if current.cheapest10_median and current.cheapest10_median > current.cheapest5_median * cfg.tail_ratio:
            conf *= 0.85
            notes.append("price ladder steps up sharply after the 5 cheapest asks")
    elif n > 0:
        executable = current.cheapest3_median or current.cheapest5_median or current.median
        thin_hist_w = cfg.thin_market_history_weight
        fv, parts = _blend([("cheapest asks median", executable, 1 - thin_hist_w),
                            ("own 30d median", hist, thin_hist_w)])
        conf *= _thin_market_factor(n)
        notes.append(f"thin market ({n} valid listing{'s' if n != 1 else ''}): " + ", ".join(parts))
        flags.append("thin_market")
    elif hist:
        fv = hist
        conf *= 0.5
        notes.append(f"no valid listings now — own 30d median {hist:.0f} (stale)")
    elif history.median_90d:
        fv = history.median_90d
        conf *= 0.35
        notes.append(f"only 90d history available ({history.median_90d:.0f})")
    else:
        return FairValue(None, None, None, 0.0, ["no market data"], ["no_data"])
    assert fv is not None

    if not hist and n > 0:
        conf *= 0.9
        notes.append("no own price history yet")

    if current.has_expensive_tail:
        flags.append("market_has_expensive_tail")
        notes.append(f"expensive tail ignored: trimmed median {current.trimmed_median:.0f} vs "
                     f"cheapest-5 {current.cheapest5_median:.0f}")
    if current.low_is_outlier:
        flags.append("lowest_listing_outlier")
        notes.append(f"lowest ask {current.low:.0f} is far below the cheapest-5 median — not used as fair value")

    executable_now = current.cheapest5_median if n >= cfg.min_listings_for_executable else current.cheapest3_median
    if history.trend_30d is not None and history.trend_30d < -0.05 and executable_now and hist:
        fv = min(fv, executable_now)
        notes.append(f"falling market ({history.trend_30d:+.1%}) — capped at current executable price")

    spread = 0.08
    if current.dispersion is not None and current.dispersion > cfg.high_dispersion:
        conf *= 0.75
        spread += 0.1
        flags.append("high_dispersion")
        notes.append(f"high dispersion among the cheapest asks ({current.dispersion:.2f})")
    if history.volatility_30d is not None and history.volatility_30d > cfg.high_volatility:
        conf *= 0.8
        spread += 0.07
        flags.append("volatile")
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
        flags=flags,
    )

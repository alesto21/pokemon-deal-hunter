"""Pure price statistics over a list of current asking prices."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class PriceStats:
    low: float | None
    median: float | None             # broad median of all valid listings
    trimmed_median: float | None
    cheapest5_median: float | None
    count: int
    seller_count: int | None
    dispersion: float | None         # (p75 - p25) / median over the cheapest 10 (the buyable market)
    cheapest3_median: float | None = None
    cheapest10_median: float | None = None
    has_expensive_tail: bool = False  # trimmed median well above the cheapest-5 median
    low_is_outlier: bool = False      # lowest ask far below the cheapest-5 median


def _quantile(sorted_vals: list[float], q: float) -> float:
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def trimmed_median(values: list[float], trim_fraction: float = 0.2) -> float | None:
    """Median after dropping the top ``trim_fraction`` of prices (outlier asks).

    We only trim the expensive tail: absurd asks are common, while cheap outliers
    are exactly the signal we want to keep visible via ``low``.
    """
    if not values:
        return None
    vals = sorted(values)
    keep = max(1, len(vals) - int(len(vals) * trim_fraction))
    return statistics.median(vals[:keep])


def cheapest_median(sorted_vals: list[float], n: int, min_count: int | None = None) -> float | None:
    """Median of the ``n`` cheapest prices; None when fewer than ``min_count`` (default n) exist."""
    if len(sorted_vals) < (n if min_count is None else min_count):
        return None
    return round(statistics.median(sorted_vals[:n]), 2)


def compute_stats(prices: list[float], sellers: list[str] | None = None, trim_fraction: float = 0.2,
                  tail_ratio: float = 1.30, low_outlier_ratio: float = 0.70) -> PriceStats:
    vals = sorted(p for p in prices if p is not None and p > 0)
    if not vals:
        return PriceStats(None, None, None, None, 0, 0 if sellers is not None else None, None)
    med = statistics.median(vals)
    window = vals[:10]
    window_med = statistics.median(window)
    dispersion = None
    if len(window) >= 4 and window_med > 0:
        dispersion = round((_quantile(window, 0.75) - _quantile(window, 0.25)) / window_med, 4)
    c5 = round(statistics.median(vals[:5]), 2)  # with <5 listings: median of what exists
    trimmed = round(trimmed_median(vals, trim_fraction) or 0, 2)
    return PriceStats(
        low=vals[0],
        median=round(med, 2),
        trimmed_median=trimmed,
        cheapest5_median=c5,
        count=len(vals),
        seller_count=len(set(sellers)) if sellers is not None else None,
        dispersion=dispersion,
        cheapest3_median=round(statistics.median(vals[:3]), 2),
        cheapest10_median=cheapest_median(vals, 10),
        has_expensive_tail=len(vals) >= 5 and trimmed > c5 * tail_ratio,
        low_is_outlier=len(vals) >= 3 and vals[0] < c5 * low_outlier_ratio,
    )


def interpolate(curve: list[tuple[float, float]] | list[list[float]], x: float) -> float:
    """Piecewise-linear lookup used for all configurable score curves."""
    pts = sorted((float(a), float(b)) for a, b in curve)
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:], strict=False):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 != x0 else y1
    return pts[-1][1]

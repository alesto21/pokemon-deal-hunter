"""Pure price statistics over a list of current asking prices."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class PriceStats:
    low: float | None
    median: float | None
    trimmed_median: float | None
    cheapest5_median: float | None
    count: int
    seller_count: int | None
    dispersion: float | None  # (p75 - p25) / median


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


def compute_stats(prices: list[float], sellers: list[str] | None = None, trim_fraction: float = 0.2) -> PriceStats:
    vals = sorted(p for p in prices if p is not None and p > 0)
    if not vals:
        return PriceStats(None, None, None, None, 0, 0 if sellers is not None else None, None)
    med = statistics.median(vals)
    dispersion = None
    if len(vals) >= 4 and med > 0:
        dispersion = round((_quantile(vals, 0.75) - _quantile(vals, 0.25)) / med, 4)
    return PriceStats(
        low=vals[0],
        median=round(med, 2),
        trimmed_median=round(trimmed_median(vals, trim_fraction) or 0, 2),
        cheapest5_median=round(statistics.median(vals[:5]), 2),
        count=len(vals),
        seller_count=len(set(sellers)) if sellers is not None else None,
        dispersion=dispersion,
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

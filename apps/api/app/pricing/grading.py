"""Grading economics from manually-entered PSA references. No paid API."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import GradingConfig
from app.pricing.stats import interpolate


@dataclass
class GradingEconomics:
    psa9_nok: float | None
    psa10_nok: float | None
    upside_psa10: float | None     # (PSA10 - raw - cost) / raw
    upside_psa9: float | None      # (PSA9  - raw - cost) / raw
    score: float | None            # 0..1 component score, None when unknown
    label: str
    flags: list[str] = field(default_factory=list)


def grading_economics(raw_value: float | None, psa9: float | None, psa10: float | None,
                      cfg: GradingConfig) -> GradingEconomics:
    cost = cfg.estimated_grading_cost_nok
    if not raw_value or raw_value <= 0 or not psa10:
        return GradingEconomics(psa9, psa10, None, None, None, "Unknown")
    up10 = (psa10 - raw_value - cost) / raw_value
    up9 = (psa9 - raw_value - cost) / raw_value if psa9 else None
    score = interpolate(cfg.upside_curve, up10)
    flags: list[str] = []
    if up9 is not None and up9 < cfg.psa9_min_margin:
        flags.append("PSA9 barely exceeds raw + grading cost")
        if up10 > 0.5:
            flags.append("economics only work at PSA10")
        score *= 0.7  # a 10 is never guaranteed
    if up10 > 1.0:
        flags.append("PSA10 premium is unusually large")
    if up10 <= 0:
        label = "None"
    elif score >= 0.7:
        label = "Strong"
    elif score >= 0.4:
        label = "Moderate"
    else:
        label = "Weak"
    return GradingEconomics(psa9, psa10, round(up10, 3), round(up9, 3) if up9 is not None else None,
                            round(score, 3), label, flags)

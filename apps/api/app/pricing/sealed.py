"""Sealed product normalisation. Deliberately makes no expected-value claims."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.pricing.stats import interpolate


@dataclass
class SealedAnalysis:
    pack_count: int | None
    price_per_pack_nok: float | None
    loose_pack_value_nok: float | None
    equivalent_pack_value_nok: float | None
    sealed_premium: float | None           # market price vs loose packs
    listing_vs_packs: float | None          # listing price vs loose packs (negative = cheaper)
    product_age_years: float | None
    top_chase_value_nok: float | None
    rip_score: float                        # 0..1 — attractive to open?
    sealed_investment_score: float          # 0..1 — attractive to hold sealed?
    notes: list[str] = field(default_factory=list)


def analyse_sealed(
    total_price_nok: float,
    pack_count: int | None,
    loose_pack_value_nok: float | None,
    sealed_market_nok: float | None,
    release_date: date | None,
    set_desirability: float,
    top_chase_value_nok: float | None,
    trend_30d: float | None,
) -> SealedAnalysis:
    notes: list[str] = []
    ppp = round(total_price_nok / pack_count, 2) if pack_count else None
    equiv = round(loose_pack_value_nok * pack_count, 2) if (loose_pack_value_nok and pack_count) else None
    premium = round((sealed_market_nok - equiv) / equiv, 3) if (sealed_market_nok and equiv) else None
    vs_packs = round((total_price_nok - equiv) / equiv, 3) if equiv else None
    age = round((date.today() - release_date).days / 365.25, 2) if release_date else None

    # Rip score: cheap per pack vs loose + desirable set + valuable chase cards.
    rip = 0.35 * set_desirability
    if vs_packs is not None:
        rip += 0.45 * interpolate([(-0.3, 1.0), (0.0, 0.5), (0.2, 0.0)], vs_packs)
        notes.append(f"{abs(vs_packs):.0%} {'below' if vs_packs < 0 else 'above'} loose-pack value")
    else:
        rip += 0.45 * 0.3
        notes.append("no loose-pack price known")
    if top_chase_value_nok:
        rip += 0.2 * interpolate([(200, 0.0), (1000, 0.6), (3000, 1.0)], top_chase_value_nok)
        notes.append(f"top chase card ≈ {top_chase_value_nok:.0f} NOK")

    # Sealed investment: older + desirable + rising + not already at huge premium.
    inv = 0.4 * set_desirability
    inv += 0.25 * (interpolate([(0, 0.2), (1.5, 0.6), (3, 1.0)], age) if age is not None else 0.3)
    inv += 0.2 * (interpolate([(-0.1, 0.0), (0.0, 0.5), (0.1, 1.0)], trend_30d) if trend_30d is not None else 0.4)
    inv += 0.15 * (interpolate([(0.0, 1.0), (0.5, 0.5), (1.5, 0.0)], premium) if premium is not None else 0.5)
    notes.append("rip score is not an EV estimate — no pull-rate EV data is used")
    return SealedAnalysis(pack_count, ppp, loose_pack_value_nok, equiv, premium, vs_packs, age,
                          top_chase_value_nok, round(min(rip, 1.0), 3), round(min(inv, 1.0), 3), notes)

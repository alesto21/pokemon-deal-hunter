"""Portfolio-aware score modifiers (pure functions, easy to test)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import BinderModifiers


@dataclass
class PortfolioState:
    owned_quantity: int = 0
    owned_in_premium: bool = False
    is_high_priority: bool = False
    is_iconic: bool = False
    owns_pokemon_in_binder: bool = False     # any card of this Pokémon already owned
    theme_name: str | None = None
    theme_owned: int = 0                      # distinct theme members already owned
    theme_size: int = 0
    distinct_pokemon_owned: int = 0


@dataclass
class PortfolioModifier:
    points: float
    items: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


def portfolio_modifier(state: PortfolioState, discount: float | None, binder_fit: str | None,
                       cfg: BinderModifiers) -> PortfolioModifier:
    items: dict[str, float] = {}
    reasons: list[str] = []
    discount = discount or 0.0

    if state.owned_quantity > 0:
        if discount > cfg.duplicate_exceptional_discount:
            reasons.append(f"already owned, but exceptional discount ({discount:.0%}) — no duplicate penalty")
        elif state.owned_in_premium:
            items["duplicate_in_premium"] = cfg.duplicate_in_premium
            reasons.append("already in premium binder (duplicate)")
        else:
            items["duplicate_other"] = cfg.duplicate_other
            reasons.append("already owned (duplicate)")
    else:
        if state.is_high_priority:
            items["missing_high_priority"] = cfg.missing_high_priority
            reasons.append("high-priority card missing from collection")
        if state.is_iconic and not state.owns_pokemon_in_binder and binder_fit in ("premium", "regular"):
            items["iconic_missing"] = cfg.iconic_missing_from_binder
            reasons.append("iconic Pokémon not yet in binder")
        if state.theme_name and state.theme_owned >= 2 and state.theme_owned < state.theme_size:
            items["completes_theme"] = cfg.completes_set_or_theme
            reasons.append(f"extends {state.theme_name} theme ({state.theme_owned}/{state.theme_size} owned)")
        if not state.owns_pokemon_in_binder and state.distinct_pokemon_owned > 0:
            items["diversification"] = cfg.improves_diversification
            reasons.append("improves binder diversification")

    bonus = sum(v for v in items.values() if v > 0)
    penalty = sum(v for v in items.values() if v < 0)
    points = min(bonus, cfg.max_total_bonus) + penalty
    return PortfolioModifier(round(points, 2), items, reasons)

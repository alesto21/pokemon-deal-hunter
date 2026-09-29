"""Portfolio queries and valuation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import UserConfig
from app.db.models import (
    BinderType,
    Card,
    EntityType,
    GradedPriceReference,
    PortfolioItem,
    PortfolioSnapshot,
)
from app.matching.normalize import fold
from app.portfolio.modifiers import PortfolioState


def name_in(names: list[str], pokemon: str | None) -> bool:
    if not pokemon:
        return False
    target = fold(pokemon)
    return any(re.search(rf"(?<![\w-]){re.escape(fold(n))}(?![\w-])", target) for n in names)


def portfolio_state_for_card(session: Session, card: Card, cfg: UserConfig) -> PortfolioState:
    items = session.scalars(select(PortfolioItem).where(PortfolioItem.card_id.is_not(None))).all()
    owned = [i for i in items if i.card_id == card.id]
    poke = card.pokemon_name or card.name
    owned_cards = [i.card for i in items if i.card]
    owned_pokemon = {fold(c.pokemon_name or c.name) for c in owned_cards}
    state = PortfolioState(
        owned_quantity=sum(i.quantity for i in owned),
        owned_in_premium=any(i.binder_type == BinderType.PREMIUM for i in owned),
        is_high_priority=name_in(cfg.pokemon.high_priority, poke),
        is_iconic=name_in(cfg.pokemon.popularity_tiers.get("iconic").names
                          if cfg.pokemon.popularity_tiers.get("iconic") else [], poke),
        owns_pokemon_in_binder=any(name_in([c.pokemon_name or c.name], poke) for c in owned_cards),
        distinct_pokemon_owned=len(owned_pokemon),
    )
    for theme, members in cfg.pokemon.themes.items():
        if name_in(members, poke):
            owned_members = {m for m in members if any(name_in([m], c.pokemon_name or c.name) for c in owned_cards)}
            state.theme_name, state.theme_owned, state.theme_size = theme, len(owned_members), len(members)
            break
    return state


@dataclass
class HoldingValue:
    item: PortfolioItem
    unit_raw_value: float | None
    unit_graded_value: float | None

    @property
    def cost(self) -> float:
        return self.item.acquisition_price_nok * self.item.quantity

    @property
    def value(self) -> float:
        unit = self.unit_graded_value if self.unit_graded_value is not None else self.unit_raw_value
        return (unit or 0.0) * self.item.quantity

    @property
    def gain(self) -> float:
        return self.value - self.cost

    @property
    def gain_pct(self) -> float | None:
        return self.gain / self.cost if self.cost else None


def graded_reference(session: Session, card_id: int, grade: float, company: str = "PSA") -> float | None:
    ref = session.scalar(
        select(GradedPriceReference)
        .where(GradedPriceReference.card_id == card_id, GradedPriceReference.grade == grade,
               GradedPriceReference.grade_company == company)
        .order_by(GradedPriceReference.updated_at.desc()).limit(1))
    return ref.price_nok if ref else None


def value_holdings(session: Session, fair_value_fn) -> list[HoldingValue]:
    """``fair_value_fn(entity_type, entity_id) -> float | None`` supplies raw values."""
    out: list[HoldingValue] = []
    for item in session.scalars(select(PortfolioItem)).all():
        if item.card_id:
            raw = fair_value_fn(EntityType.CARD, item.card_id)
            graded = None
            if item.grading_status == "graded" and item.psa_grade:
                graded = graded_reference(session, item.card_id, item.psa_grade, item.grade_company or "PSA")
        else:
            raw = fair_value_fn(EntityType.PRODUCT, item.product_id) if item.product_id else None
            graded = None
        out.append(HoldingValue(item, raw, graded))
    return out


def portfolio_summary(session: Session, holdings: list[HoldingValue]) -> dict:
    cost = sum(h.cost for h in holdings)
    raw_value = sum((h.unit_raw_value or 0) * h.item.quantity for h in holdings
                    if h.unit_graded_value is None)
    graded_value = sum((h.unit_graded_value or 0) * h.item.quantity for h in holdings
                       if h.unit_graded_value is not None)
    by_binder: dict[str, float] = {}
    for h in holdings:
        by_binder[h.item.binder_type] = round(by_binder.get(h.item.binder_type, 0) + h.value, 2)
    total = raw_value + graded_value
    past = session.scalar(select(PortfolioSnapshot).where(PortfolioSnapshot.day <= date.today() - timedelta(days=30))
                          .order_by(PortfolioSnapshot.day.desc()).limit(1))
    past_total = (past.raw_value_nok + past.graded_value_nok) if past else None
    return {
        "total_cost_nok": round(cost, 2),
        "raw_value_nok": round(raw_value, 2),
        "graded_value_nok": round(graded_value, 2),
        "total_value_nok": round(total, 2),
        "unrealized_gain_nok": round(total - cost, 2),
        "unrealized_gain_pct": round((total - cost) / cost, 4) if cost else None,
        "by_binder": by_binder,
        "change_30d_nok": round(total - past_total, 2) if past_total is not None else None,
        "item_count": sum(h.item.quantity for h in holdings),
    }


def take_portfolio_snapshot(session: Session, holdings: list[HoldingValue]) -> PortfolioSnapshot:
    summary = portfolio_summary(session, holdings)
    today = date.today()
    snap = session.scalar(select(PortfolioSnapshot).where(PortfolioSnapshot.day == today))
    if not snap:
        snap = PortfolioSnapshot(day=today, total_cost_nok=0, raw_value_nok=0, graded_value_nok=0)
        session.add(snap)
    snap.total_cost_nok = summary["total_cost_nok"]
    snap.raw_value_nok = summary["raw_value_nok"]
    snap.graded_value_nok = summary["graded_value_nok"]
    snap.by_binder = summary["by_binder"]
    return snap

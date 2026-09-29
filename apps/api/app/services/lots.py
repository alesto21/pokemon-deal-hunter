"""Manual lot / collection valuation. Image recognition is a phase-2 extension point."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EntityType, Lot
from app.pricing.fair_value import FairValue
from app.services.market import market_view

LOT_LIQUIDITY_HAIRCUT = 0.85  # selling singles out of a lot costs time, fees and shipping


@dataclass
class LotValuation:
    estimated_value_nok: float
    conservative_value_nok: float
    priced_items: int
    total_items: int
    lines: list[dict] = field(default_factory=list)

    def as_fair_value(self) -> FairValue:
        coverage = self.priced_items / self.total_items if self.total_items else 0
        return FairValue(
            fair_value_nok=round(self.conservative_value_nok, 2),
            fair_value_low=round(self.conservative_value_nok * 0.9, 2),
            fair_value_high=round(self.estimated_value_nok, 2),
            confidence=round(0.55 * coverage, 3),
            explanation=[f"lot: {self.priced_items}/{self.total_items} items priced; conservative value uses "
                         f"low fair values × {LOT_LIQUIDITY_HAIRCUT}"],
        )


class LotImageAnalyzer:
    """Phase-2 hook: detect cards in uploaded lot images. Not implemented in v1."""

    def detect(self, image_path: str) -> list[dict]:
        raise NotImplementedError("Lot image recognition is planned for phase 2")


def value_lot(session: Session, lot: Lot) -> LotValuation:
    est = cons = 0.0
    priced = 0
    lines = []
    for item in lot.items:
        unit = low = None
        if item.manual_value_nok is not None:
            unit = low = item.manual_value_nok
        elif item.card_id or item.product_id:
            etype = EntityType.CARD if item.card_id else EntityType.PRODUCT
            fv = market_view(session, etype, item.card_id or item.product_id).fair_value  # type: ignore[arg-type]
            unit, low = fv.fair_value_nok, fv.fair_value_low
        if unit is not None:
            priced += 1
            est += unit * item.quantity
            cons += (low or unit) * item.quantity * LOT_LIQUIDITY_HAIRCUT
        lines.append({"id": item.id, "label": item.label, "card_id": item.card_id, "product_id": item.product_id,
                      "quantity": item.quantity, "unit_value_nok": unit})
    return LotValuation(round(est, 2), round(cons, 2), priced, len(lot.items), lines)


def lot_for_listing(session: Session, listing_id: int) -> Lot | None:
    return session.scalar(select(Lot).where(Lot.listing_id == listing_id))

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
    """Value of the IDENTIFIED part of a lot only. Unidentified items count as 0 — never guessed."""

    estimated_value_nok: float
    conservative_value_nok: float
    priced_items: int
    total_items: int
    lines: list[dict] = field(default_factory=list)
    priced_quantity: int = 0
    total_quantity: int | None = None   # stated by the listing, or enumerated by you; None = unknown
    stated_quantity: int | None = None

    @property
    def coverage(self) -> float | None:
        """Share of the lot's items that are identified and priced. None = total unknown."""
        if not self.total_quantity:
            return None
        return round(min(1.0, self.priced_quantity / self.total_quantity), 4)

    @property
    def unidentified(self) -> int | None:
        return None if self.total_quantity is None else max(self.total_quantity - self.priced_quantity, 0)

    def as_fair_value(self) -> FairValue:
        cov = self.coverage
        unid = "unknown number of" if self.unidentified is None else str(self.unidentified)
        return FairValue(
            fair_value_nok=round(self.conservative_value_nok, 2),
            fair_value_low=round(self.conservative_value_nok * 0.9, 2),
            fair_value_high=round(self.estimated_value_nok, 2),
            confidence=round(0.55 * (cov or 0.0), 3),
            explanation=[f"lot: value of {self.priced_quantity} identified item(s) only; {unid} item(s) "
                         f"unidentified and valued at 0",
                         f"conservative value uses low fair values × {LOT_LIQUIDITY_HAIRCUT}"],
            flags=["lot_partial_value"] if cov is None or cov < 1 else [],
        )


class LotImageAnalyzer:
    """Phase-2 hook: detect cards in uploaded lot images. Not implemented in v1."""

    def detect(self, image_path: str) -> list[dict]:
        raise NotImplementedError("Lot image recognition is planned for phase 2")


def value_lot(session: Session, lot: Lot) -> LotValuation:
    est = cons = 0.0
    priced = priced_qty = 0
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
            priced_qty += item.quantity
            est += unit * item.quantity
            cons += (low or unit) * item.quantity * LOT_LIQUIDITY_HAIRCUT
        lines.append({"id": item.id, "label": item.label, "card_id": item.card_id, "product_id": item.product_id,
                      "quantity": item.quantity, "unit_value_nok": unit})
    listed_qty = sum(i.quantity for i in lot.items)
    if lot.stated_quantity:
        total_qty: int | None = max(lot.stated_quantity, listed_qty)
    elif lot.items and all(i.origin == "manual" for i in lot.items):
        total_qty = listed_qty  # you enumerated the lot yourself
    else:
        total_qty = None        # the listing doesn't say how many items it has
    return LotValuation(round(est, 2), round(cons, 2), priced, len(lot.items), lines, priced_qty, total_qty,
                        lot.stated_quantity)


def lot_for_listing(session: Session, listing_id: int) -> Lot | None:
    return session.scalar(select(Lot).where(Lot.listing_id == listing_id))

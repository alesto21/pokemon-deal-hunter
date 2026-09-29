from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import PortfolioIn, PortfolioPatch
from app.api.serializers import portfolio_item_out
from app.db.models import Card, PortfolioItem, PortfolioSnapshot, Product
from app.db.session import get_db
from app.portfolio.service import HoldingValue, portfolio_summary, value_holdings
from app.services.market import fair_value_nok

router = APIRouter(tags=["portfolio"])


def _holding_out(h: HoldingValue) -> dict:
    d = portfolio_item_out(h.item)
    d.update(unit_raw_value_nok=h.unit_raw_value, unit_graded_value_nok=h.unit_graded_value,
             cost_nok=round(h.cost, 2), value_nok=round(h.value, 2), gain_nok=round(h.gain, 2),
             gain_pct=round(h.gain_pct, 4) if h.gain_pct is not None else None)
    return d


def _holdings(db: Session) -> list[HoldingValue]:
    return value_holdings(db, lambda t, i: fair_value_nok(db, t, i))


@router.get("/portfolio")
def list_portfolio(db: Session = Depends(get_db), binder_type: str | None = None) -> list[dict]:
    hs = _holdings(db)
    if binder_type:
        hs = [h for h in hs if h.item.binder_type == binder_type]
    return [_holding_out(h) for h in sorted(hs, key=lambda h: -h.value)]


@router.get("/portfolio/summary")
def summary(db: Session = Depends(get_db)) -> dict:
    hs = _holdings(db)
    out = portfolio_summary(db, hs)
    priced = [h for h in hs if h.gain_pct is not None and (h.unit_raw_value or h.unit_graded_value)]
    out["top_holdings"] = [_holding_out(h) for h in sorted(hs, key=lambda h: -h.value)[:10]]
    out["best_performers"] = [_holding_out(h) for h in sorted(priced, key=lambda h: -(h.gain_pct or 0))[:5]]
    out["worst_performers"] = [_holding_out(h) for h in sorted(priced, key=lambda h: h.gain_pct or 0)[:5]]
    recent = sorted(hs, key=lambda h: (h.item.acquisition_date or h.item.created_at.date()), reverse=True)[:10]
    out["recent_purchases"] = [_holding_out(h) for h in recent]
    snaps = db.scalars(select(PortfolioSnapshot).order_by(PortfolioSnapshot.day)).all()
    out["history"] = [{"day": s.day, "cost": s.total_cost_nok, "value": s.raw_value_nok + s.graded_value_nok}
                      for s in snaps]
    return out


@router.post("/portfolio", status_code=201)
def add_item(body: PortfolioIn, db: Session = Depends(get_db)) -> dict:
    if bool(body.card_id) == bool(body.product_id):
        raise HTTPException(422, "Provide exactly one of card_id or product_id")
    if body.card_id and not db.get(Card, body.card_id):
        raise HTTPException(404, "Card not found")
    if body.product_id and not db.get(Product, body.product_id):
        raise HTTPException(404, "Product not found")
    item = PortfolioItem(**body.model_dump())
    db.add(item)
    db.flush()
    db.refresh(item)
    return portfolio_item_out(item)


@router.patch("/portfolio/{item_id}")
def patch_item(item_id: int, body: PortfolioPatch, db: Session = Depends(get_db)) -> dict:
    item = db.get(PortfolioItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    return portfolio_item_out(item)


@router.delete("/portfolio/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)) -> None:
    item = db.get(PortfolioItem, item_id)
    if item:
        db.delete(item)

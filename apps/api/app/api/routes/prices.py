from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import Card, PortfolioItem, PriceSnapshot, Product
from app.db.session import get_db
from app.pricing.history import daily_series
from app.services.market import market_view

router = APIRouter(tags=["prices"])


@router.get("/prices/{entity_type}/{entity_id}")
def price_history(entity_type: str, entity_id: int, days: int = Query(default=90, ge=1, le=3650),
                  db: Session = Depends(get_db)) -> dict:
    if entity_type not in ("card", "product"):
        raise HTTPException(422, "entity_type must be card or product")
    entity = db.get(Card if entity_type == "card" else Product, entity_id)
    if not entity:
        raise HTTPException(404, "Not found")
    daily = daily_series(db, entity_type, entity_id, days)
    raw = db.scalars(select(PriceSnapshot).where(
        PriceSnapshot.entity_type == entity_type, PriceSnapshot.entity_id == entity_id,
        PriceSnapshot.timestamp >= utcnow() - timedelta(days=min(days, 30))).order_by(PriceSnapshot.timestamp)).all()
    col = PortfolioItem.card_id if entity_type == "card" else PortfolioItem.product_id
    entries = db.scalars(select(PortfolioItem).where(col == entity_id)).all()
    view = market_view(db, entity_type, entity_id)
    label = f"{entity.name} {getattr(entity, 'card_number', '') or ''}".strip()
    return {
        "entity_type": entity_type, "entity_id": entity_id, "label": label,
        "set_name": entity.set_name,
        "daily": [{"day": d.day, "low": d.low_price, "median": d.median_price, "trimmed_median": d.trimmed_median,
                   "listing_count": d.listing_count} for d in daily],
        "raw": [{"timestamp": s.timestamp, "low": s.low_price, "median": s.median_price,
                 "trimmed_median": s.trimmed_median, "listing_count": s.listing_count} for s in raw],
        "portfolio_entries": [{"date": i.acquisition_date, "price_nok": i.acquisition_price_nok,
                               "quantity": i.quantity} for i in entries],
        "fair_value": view.fair_value.__dict__, "history": view.history.__dict__, "current": view.current.__dict__,
    }

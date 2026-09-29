from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import WatchlistIn, WatchlistPatch
from app.api.serializers import watchlist_out
from app.db.models import Card, Product, WatchlistItem
from app.db.session import get_db
from app.services.market import fair_value_nok

router = APIRouter(tags=["watchlist"])


def _label(db: Session, w: WatchlistItem) -> str | None:
    if w.target_type == "card":
        c = db.get(Card, w.entity_id)
        return f"{c.name} {c.card_number or ''} ({c.set_name})" if c else None
    p = db.get(Product, w.entity_id)
    return p.name if p else None


def _out(db: Session, w: WatchlistItem) -> dict:
    return watchlist_out(w, _label(db, w), fair_value_nok(db, w.target_type, w.entity_id))


@router.get("/watchlist")
def list_watchlist(db: Session = Depends(get_db)) -> list[dict]:
    return [_out(db, w) for w in db.scalars(select(WatchlistItem).order_by(WatchlistItem.priority)).all()]


@router.post("/watchlist", status_code=201)
def add_watch(body: WatchlistIn, db: Session = Depends(get_db)) -> dict:
    model = Card if body.target_type == "card" else Product
    if not db.get(model, body.entity_id):
        raise HTTPException(404, f"{body.target_type} not found")
    w = WatchlistItem(**body.model_dump())
    db.add(w)
    db.flush()
    return _out(db, w)


@router.patch("/watchlist/{item_id}")
def patch_watch(item_id: int, body: WatchlistPatch, db: Session = Depends(get_db)) -> dict:
    w = db.get(WatchlistItem, item_id)
    if not w:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(w, k, v)
    return _out(db, w)


@router.delete("/watchlist/{item_id}", status_code=204)
def delete_watch(item_id: int, db: Session = Depends(get_db)) -> None:
    w = db.get(WatchlistItem, item_id)
    if w:
        db.delete(w)

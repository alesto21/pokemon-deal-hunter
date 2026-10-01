"""Read-only dashboard read models (one call per page)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import dashboard as d

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    return d.overview(db)


@router.get("/deals")
def deals(db: Session = Depends(get_db), level: list[str] | None = Query(default=None), source: str | None = None,
          seller_region: str | None = None, pokemon: str | None = None, set_code: str | None = None,
          min_landed: float | None = None, max_landed: float | None = None, min_discount: float | None = None,
          min_confidence: float | None = None, min_score: float | None = None, q: str | None = None,
          status: str = "active", sort: str = "score", limit: int = Query(default=100, le=500),
          offset: int = 0) -> dict:
    return d.deals(db, level, source, seller_region, pokemon, set_code, min_landed, max_landed, min_discount,
                   min_confidence, min_score, q, status, sort, limit, offset)


@router.get("/deals/{listing_id}")
def deal(listing_id: int, db: Session = Depends(get_db)) -> dict:
    out = d.deal_detail(db, listing_id)
    if out is None:
        raise HTTPException(404, "No evaluated listing with that id")
    return out


@router.get("/portfolio")
def portfolio(db: Session = Depends(get_db)) -> dict:
    return d.portfolio_page(db)


@router.get("/binder/{binder_type}")
def binder(binder_type: str, db: Session = Depends(get_db)) -> dict:
    if binder_type not in ("premium", "regular"):
        raise HTTPException(404, "binder_type must be premium or regular")
    return d.binder(db, binder_type)


@router.get("/sealed")
def sealed(db: Session = Depends(get_db)) -> dict:
    return d.sealed(db)


@router.get("/grading")
def grading(db: Session = Depends(get_db)) -> dict:
    return d.grading(db)


@router.get("/watchlist")
def watchlist(db: Session = Depends(get_db)) -> dict:
    return d.watchlist(db)


@router.get("/market")
def market(db: Session = Depends(get_db), window_days: int = Query(default=30, ge=2, le=365)) -> dict:
    return d.market(db, window_days)


@router.get("/market/series/{entity_type}/{entity_id}")
def market_series(entity_type: str, entity_id: int, days: int = Query(default=90, ge=1, le=3650),
                  db: Session = Depends(get_db)) -> dict:
    if entity_type not in ("card", "product"):
        raise HTTPException(422, "entity_type must be card or product")
    out = d.market_series(db, entity_type, entity_id, days)
    if out is None:
        raise HTTPException(404, "Not found")
    return out


@router.get("/alerts")
def alerts(db: Session = Depends(get_db), days: int = Query(default=7, ge=1, le=90)) -> dict:
    return d.alerts(db, days)


@router.get("/system")
def system(db: Session = Depends(get_db)) -> dict:
    return d.system(db)

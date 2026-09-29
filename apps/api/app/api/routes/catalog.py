from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.schemas import CardIn, GradedRefIn, ProductIn
from app.api.serializers import card_out, product_out
from app.core.config import get_user_config
from app.db.base import utcnow
from app.db.models import Card, EntityType, GradedPriceReference, PortfolioItem, Product, WatchlistItem
from app.db.session import get_db
from app.pricing.grading import grading_economics
from app.services.market import market_view

router = APIRouter(tags=["catalog"])


@router.get("/cards")
def search_cards(db: Session = Depends(get_db), q: str | None = None, set_code: str | None = None,
                 limit: int = Query(default=50, le=500)) -> list[dict]:
    query = select(Card)
    if q:
        like = f"%{q[:100]}%"
        query = query.where(or_(Card.name.ilike(like), Card.card_number.ilike(like), Card.set_name.ilike(like)))
    if set_code:
        query = query.where(Card.set_code == set_code)
    return [card_out(c) for c in db.scalars(query.order_by(Card.set_code, Card.name).limit(limit)).all()]


@router.post("/cards", status_code=201)
def create_card(body: CardIn, db: Session = Depends(get_db)) -> dict:
    data = body.model_dump()
    data["image_url"] = str(data["image_url"]) if data["image_url"] else None
    data["pokemon_name"] = data["pokemon_name"] or body.name
    card = Card(**data, source_ids={})
    db.add(card)
    db.flush()
    return card_out(card)  # type: ignore[return-value]


def _market(db: Session, etype: str, eid: int) -> dict:
    view = market_view(db, etype, eid)
    return {"current": view.current.__dict__, "history": view.history.__dict__,
            "fair_value": view.fair_value.__dict__}


@router.get("/cards/{card_id}")
def get_card(card_id: int, db: Session = Depends(get_db)) -> dict:
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(404, "Card not found")
    out = card_out(card) or {}
    market = _market(db, EntityType.CARD, card_id)
    refs = db.scalars(select(GradedPriceReference).where(GradedPriceReference.card_id == card_id)).all()
    out["market"] = market
    out["graded_refs"] = [_ref_out(r) for r in refs]
    psa = {r.grade: r.price_nok for r in refs if r.grade_company == "PSA"}
    g = grading_economics(market["fair_value"]["fair_value_nok"], psa.get(9), psa.get(10), get_user_config().grading)
    out["grading"] = g.__dict__
    out["owned"] = sum(i.quantity for i in db.scalars(select(PortfolioItem).where(PortfolioItem.card_id == card_id)))
    out["on_watchlist"] = db.scalar(select(WatchlistItem.id).where(
        WatchlistItem.target_type == "card", WatchlistItem.entity_id == card_id)) is not None
    return out


@router.get("/products")
def search_products(db: Session = Depends(get_db), q: str | None = None, limit: int = Query(default=50, le=500)
                    ) -> list[dict]:
    query = select(Product)
    if q:
        query = query.where(or_(Product.name.ilike(f"%{q[:100]}%"), Product.set_name.ilike(f"%{q[:100]}%")))
    return [product_out(p) for p in db.scalars(query.order_by(Product.name).limit(limit)).all()]


@router.post("/products", status_code=201)
def create_product(body: ProductIn, db: Session = Depends(get_db)) -> dict:
    p = Product(**body.model_dump(), source_ids={})
    if p.pack_count is None:
        p.pack_count = get_user_config().sets.pack_counts.get(p.product_type)
    db.add(p)
    db.flush()
    return product_out(p)  # type: ignore[return-value]


@router.get("/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)) -> dict:
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(404, "Product not found")
    out = product_out(p) or {}
    out["market"] = _market(db, EntityType.PRODUCT, product_id)
    return out


# ------------------------------------------------------------------ graded references
def _ref_out(r: GradedPriceReference) -> dict:
    return {"id": r.id, "card_id": r.card_id, "grade_company": r.grade_company, "grade": r.grade,
            "price_nok": r.price_nok, "source": r.source, "updated_at": r.updated_at, "confidence": r.confidence}


def upsert_graded(db: Session, body: GradedRefIn) -> GradedPriceReference:
    ref = db.scalar(select(GradedPriceReference).where(
        GradedPriceReference.card_id == body.card_id, GradedPriceReference.grade_company == body.grade_company.upper(),
        GradedPriceReference.grade == body.grade, GradedPriceReference.source == body.source))
    if not ref:
        ref = GradedPriceReference(card_id=body.card_id, grade_company=body.grade_company.upper(), grade=body.grade,
                                   source=body.source, price_nok=body.price_nok)
        db.add(ref)
    ref.price_nok, ref.confidence, ref.updated_at = body.price_nok, body.confidence, utcnow()
    db.flush()
    return ref


@router.get("/graded")
def list_graded(db: Session = Depends(get_db), card_id: int | None = None) -> list[dict]:
    q = select(GradedPriceReference)
    if card_id:
        q = q.where(GradedPriceReference.card_id == card_id)
    rows = db.scalars(q.order_by(GradedPriceReference.updated_at.desc()).limit(500)).all()
    out = []
    for r in rows:
        d = _ref_out(r)
        card = db.get(Card, r.card_id)
        d["card_label"] = f"{card.name} {card.card_number or ''} ({card.set_name})" if card else None
        out.append(d)
    return out


@router.post("/graded", status_code=201)
def add_graded(body: GradedRefIn, db: Session = Depends(get_db)) -> dict:
    if not db.get(Card, body.card_id):
        raise HTTPException(404, "Card not found")
    return _ref_out(upsert_graded(db, body))


@router.delete("/graded/{ref_id}", status_code=204)
def delete_graded(ref_id: int, db: Session = Depends(get_db)) -> None:
    ref = db.get(GradedPriceReference, ref_id)
    if ref:
        db.delete(ref)


@router.post("/graded/import")
async def import_graded(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    """CSV columns: card_id OR (set_code, card_number); grade_company, grade, price_nok[, source, confidence]."""
    raw = (await file.read(1_000_001)).decode("utf-8-sig")
    ok, errors = 0, []
    for i, row in enumerate(csv.DictReader(io.StringIO(raw)), start=1):
        try:
            card_id = int(row["card_id"]) if row.get("card_id") else None
            if card_id is None:
                card = db.scalar(select(Card).where(Card.set_code == (row.get("set_code") or "").upper(),
                                                    Card.card_number == row.get("card_number")))
                card_id = card.id if card else None
            if card_id is None or not db.get(Card, card_id):
                raise ValueError("card not found")
            upsert_graded(db, GradedRefIn(card_id=card_id, grade_company=row.get("grade_company") or "PSA",
                                          grade=float(row["grade"]), price_nok=float(row["price_nok"]),
                                          source=row.get("source") or "csv",
                                          confidence=float(row.get("confidence") or 0.7)))
            ok += 1
        except (KeyError, ValueError) as exc:
            errors.append({"row": i, "error": str(exc)[:200]})
    return {"imported": ok, "errors": errors}

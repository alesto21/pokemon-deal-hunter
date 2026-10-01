from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import FinnCaptureIn, ListingPatch, ManualListingIn, ReviewDecision
from app.api.serializers import evaluation_out, listing_out
from app.collectors.finn import FinnIngestError, ingest_url, parse_import
from app.core.security import InvalidURLError
from app.db.models import Card, DealEvaluation, Listing, MatchStatus, Product
from app.db.session import get_db
from app.services.evaluation import evaluate_listing
from app.services.lots import lot_for_listing, value_lot

router = APIRouter(tags=["listings"])


def _get(db: Session, listing_id: int) -> Listing:
    listing = db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    return listing


@router.get("/listings")
def list_listings(db: Session = Depends(get_db), source: str | None = None, status: str | None = None,
                  match_status: str | None = None, limit: int = Query(default=100, le=500)) -> list[dict]:
    q = select(Listing)
    if source:
        q = q.where(Listing.source == source)
    if status:
        q = q.where(Listing.status == status)
    if match_status:
        q = q.where(Listing.match_status == match_status)
    return [listing_out(x) for x in db.scalars(q.order_by(Listing.last_seen.desc()).limit(limit)).all()]


@router.get("/listings/{listing_id}")
def get_listing(listing_id: int, db: Session = Depends(get_db)) -> dict:
    listing = _get(db, listing_id)
    evs = db.scalars(select(DealEvaluation).where(DealEvaluation.listing_id == listing_id)
                     .order_by(DealEvaluation.timestamp.desc()).limit(20)).all()
    out = listing_out(listing, evs[0] if evs else None)
    out["evaluation_history"] = [evaluation_out(e) for e in evs]
    lot = lot_for_listing(db, listing_id)
    if lot:
        v = value_lot(db, lot)
        out["lot"] = {"id": lot.id, "images": lot.images, "notes": lot.notes, "valuation": v.__dict__}
    return out


@router.post("/listings/manual", status_code=201)
def add_manual_listing(body: ManualListingIn, db: Session = Depends(get_db)) -> dict:
    try:
        listing = ingest_url(db, str(body.url), body.title, body.price, body.currency.upper(), body.shipping_nok,
                             body.condition, body.description, fetch=body.fetch_metadata)
    except (FinnIngestError, InvalidURLError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    ev, _, _ = evaluate_listing(db, listing)
    return listing_out(listing, ev)


@router.post("/finn/capture", status_code=201)
def finn_capture(body: FinnCaptureIn, db: Session = Depends(get_db)) -> dict:
    """Ingest a FINN listing captured from the user's own browser session (no app-side fetching)."""
    try:
        listing = ingest_url(db, str(body.url), body.title, body.price, "NOK", body.shipping_nok, body.condition,
                             body.description, body.seller, fetch=False, location=body.location,
                             seller_type=body.seller_type,
                             published_at=body.published_at.replace(tzinfo=None) if body.published_at else None,
                             image_urls=[str(u) for u in body.image_urls], capture_method="capture")
    except (FinnIngestError, InvalidURLError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    ev, _, _ = evaluate_listing(db, listing)
    return listing_out(listing, ev)


@router.post("/listings/import")
async def import_listings(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    raw = await file.read(2_000_001)
    if len(raw) > 2_000_000:
        raise HTTPException(413, "File too large (max 2 MB)")
    try:
        rows = parse_import(raw.decode("utf-8-sig"), file.filename or "import.csv")
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(422, f"Could not parse file: {exc}") from exc
    created, errors = [], []
    for i, r in enumerate(rows, start=1):
        try:
            with db.begin_nested():
                listing = ingest_url(db, r["url"], r["title"], r["price"], r["currency"], r["shipping_nok"],
                                     r["condition"], r["description"], capture_method="csv")
                ev, _, _ = evaluate_listing(db, listing)
            created.append({"row": i, "listing_id": listing.id, "score": ev.total_score,
                            "recommendation": ev.recommendation})
        except (FinnIngestError, InvalidURLError, ValueError) as exc:
            errors.append({"row": i, "error": str(exc)})
    return {"imported": len(created), "failed": len(errors), "items": created, "errors": errors}


@router.post("/listings/{listing_id}/evaluate")
def evaluate(listing_id: int, send_alerts: bool = False, db: Session = Depends(get_db)) -> dict:
    listing = _get(db, listing_id)
    ev, _, decision = evaluate_listing(db, listing, send_alerts=send_alerts)
    out = listing_out(listing, ev)
    out["decision"] = decision.__dict__ if decision else None
    return out


@router.patch("/listings/{listing_id}")
def patch_listing(listing_id: int, body: ListingPatch, db: Session = Depends(get_db)) -> dict:
    listing = _get(db, listing_id)
    if body.status:
        listing.status = body.status
    if body.listing_kind:
        listing.listing_kind = body.listing_kind
    return listing_out(listing)


@router.get("/review")
def review_queue(db: Session = Depends(get_db), include_unresolved: bool = True) -> list[dict]:
    statuses = [MatchStatus.REVIEW] + ([MatchStatus.UNRESOLVED] if include_unresolved else [])
    rows = db.scalars(select(Listing).where(Listing.status == "active", Listing.match_status.in_(statuses),
                                            Listing.listing_kind != "lot")
                      .order_by(Listing.confidence.desc()).limit(200)).all()
    return [listing_out(x) for x in rows]


@router.post("/review/{listing_id}")
def review_decide(listing_id: int, body: ReviewDecision, db: Session = Depends(get_db)) -> dict:
    listing = _get(db, listing_id)
    if body.action == "reject":
        listing.match_status, listing.matched_card_id, listing.matched_product_id = MatchStatus.REJECTED, None, None
        listing.confidence = 0.0
        return listing_out(listing)
    etype, eid = body.entity_type, body.entity_id
    if body.action == "accept":
        if listing.matched_card_id:
            etype, eid = "card", listing.matched_card_id
        elif listing.matched_product_id:
            etype, eid = "product", listing.matched_product_id
        elif listing.match_candidates:
            etype, eid = listing.match_candidates[0]["entity_type"], listing.match_candidates[0]["entity_id"]
    if not etype or not eid:
        raise HTTPException(422, "entity_type and entity_id required")
    model = Card if etype == "card" else Product
    if not db.get(model, eid):
        raise HTTPException(404, f"{etype} {eid} not found")
    listing.matched_card_id = eid if etype == "card" else None
    listing.matched_product_id = eid if etype == "product" else None
    listing.match_status, listing.confidence = MatchStatus.MANUAL, 1.0
    if etype == "product" and listing.listing_kind == "single":
        listing.listing_kind = "sealed"
    db.flush()
    ev, _, _ = evaluate_listing(db, listing)
    return listing_out(listing, ev)

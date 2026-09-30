from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.serializers import listing_out
from app.db.base import utcnow
from app.db.models import Alert, CollectorRun, DealEvaluation, Listing, SourceStatus
from app.db.session import get_db
from app.portfolio.service import portfolio_summary, value_holdings
from app.services.market import fair_value_nok

router = APIRouter(tags=["deals"])


def latest_evaluations_query():
    latest = (select(DealEvaluation.listing_id, func.max(DealEvaluation.id).label("ev_id"))
              .group_by(DealEvaluation.listing_id).subquery())
    return (select(Listing, DealEvaluation)
            .join(latest, latest.c.listing_id == Listing.id)
            .join(DealEvaluation, DealEvaluation.id == latest.c.ev_id))


@router.get("/deals")
def list_deals(
    db: Session = Depends(get_db),
    source: str | None = None,
    min_score: float = 0,
    recommendation: list[str] | None = Query(default=None),
    binder_fit: str | None = None,
    seller_region: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    q: str | None = None,
    status: str = "active",
    limit: int = Query(default=100, le=500),
    offset: int = 0,
) -> dict:
    level = func.coalesce(DealEvaluation.alert_level, DealEvaluation.recommendation)
    query = latest_evaluations_query().where(DealEvaluation.total_score >= min_score)
    if status != "all":
        query = query.where(Listing.status == status)
    if source:
        query = query.where(Listing.source == source)
    if recommendation:  # filters on the effective level (after caps), like the badge
        query = query.where(level.in_(recommendation))
    if binder_fit:
        query = query.where(DealEvaluation.binder_fit == binder_fit)
    landed = func.coalesce(Listing.landed_cost_nok, Listing.total_price_nok)
    if min_price is not None:
        query = query.where(landed >= min_price)
    if max_price is not None:
        query = query.where(landed <= max_price)
    if seller_region:
        query = query.where(Listing.seller_region == seller_region)
    if q:
        query = query.where(Listing.title.ilike(f"%{q[:100]}%"))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(DealEvaluation.total_score.desc()).limit(limit).offset(offset)).all()
    return {"total": total, "items": [listing_out(listing, ev) for listing, ev in rows]}


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    start = datetime.combine(utcnow().date(), datetime.min.time())
    runs = db.scalars(select(CollectorRun).where(CollectorRun.started_at >= start)).all()
    good = ["GOOD", "STRONG_BUY", "STEAL"]
    level = func.coalesce(DealEvaluation.alert_level, DealEvaluation.recommendation)
    deals_today = db.scalar(select(func.count(func.distinct(DealEvaluation.listing_id))).where(
        DealEvaluation.timestamp >= start, level.in_(good))) or 0
    alerts_today = db.scalar(select(func.count(Alert.id)).where(Alert.sent_at >= start, Alert.kind == "deal")) or 0
    sources = [{"source": s.source, "healthy": s.consecutive_failures == 0, "last_success": s.last_success,
                "last_failure": s.last_failure} for s in db.scalars(select(SourceStatus)).all()]
    summary = portfolio_summary(db, value_holdings(db, lambda t, i: fair_value_nok(db, t, i)))
    top = db.execute(latest_evaluations_query()
                     .where(Listing.status == "active", level.in_(good))
                     .order_by(DealEvaluation.total_score.desc()).limit(5)).all()
    return {
        "scans_today": len(runs),
        "failed_scans_today": sum(1 for r in runs if not r.success),
        "listings_processed_today": sum(r.items_fetched for r in runs),
        "listings_evaluated_today": sum(r.listings_evaluated for r in runs),
        "deals_found_today": deals_today,
        "alerts_sent_today": alerts_today,
        "active_listings": db.scalar(select(func.count(Listing.id)).where(Listing.status == "active")),
        "review_queue": db.scalar(select(func.count(Listing.id)).where(
            Listing.status == "active", Listing.match_status == "review")),
        "sources": sources,
        "portfolio": summary,
        "top_deals": [listing_out(listing, ev) for listing, ev in top],
    }


@router.get("/alerts")
def list_alerts(db: Session = Depends(get_db), limit: int = Query(default=50, le=500)) -> list[dict]:
    rows = db.scalars(select(Alert).order_by(Alert.sent_at.desc()).limit(limit)).all()
    return [{"id": a.id, "kind": a.kind, "severity": a.severity, "sent_at": a.sent_at, "listing_id": a.listing_id,
             "price_nok": a.price_nok, "dry_run": a.dry_run, "telegram_message_id": a.telegram_message_id,
             "message": a.message} for a in rows]

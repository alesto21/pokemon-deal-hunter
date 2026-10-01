"""Read models for the dashboard. Read-only: nothing here changes pricing, scoring or data.

Every number comes from the database or from existing domain functions (fair value, grading
economics, sealed analysis). Where data does not exist yet (no history, no PSA reference),
the value is ``None`` and the UI shows an empty state. Nothing is estimated or back-filled.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.config import get_user_config
from app.db.base import utc_today, utcnow
from app.db.models import (
    Alert,
    Card,
    DealEvaluation,
    EntityType,
    GradedPriceReference,
    Listing,
    PortfolioSnapshot,
    PriceDaily,
    PriceSnapshot,
    Product,
    WatchlistItem,
)
from app.portfolio.service import HoldingValue, portfolio_summary, value_holdings
from app.pricing.grading import grading_economics
from app.pricing.sealed import analyse_sealed
from app.services.evaluation import _loose_pack_value, _top_chase_value
from app.services.market import fair_value_nok, market_view

GOOD_PLUS = ("GOOD", "STRONG_BUY", "STEAL")
LEVEL = func.coalesce(DealEvaluation.alert_level, DealEvaluation.recommendation)


# ---------------------------------------------------------------- shared serialisers
def card_brief(c: Card | None) -> dict[str, Any] | None:
    if c is None:
        return None
    return {"type": "card", "id": c.id, "name": c.name, "pokemon": c.pokemon_name, "set_name": c.set_name,
            "set_code": c.set_code, "number": c.card_number, "rarity": c.rarity, "image_url": c.image_url}


def product_brief(p: Product | None) -> dict[str, Any] | None:
    if p is None:
        return None
    return {"type": "product", "id": p.id, "name": p.name, "product_type": p.product_type, "set_name": p.set_name,
            "set_code": p.set_code, "pack_count": p.pack_count, "image_url": p.image_url}


def entity_brief(listing: Listing) -> dict[str, Any] | None:
    return card_brief(listing.card) or product_brief(listing.product)


def deal_row(listing: Listing, ev: DealEvaluation) -> dict[str, Any]:
    r = ev.reason_json or {}
    landed = listing.scoring_price_nok
    return {
        "listing_id": listing.id, "url": listing.url, "title": listing.title, "source": listing.source,
        "seller": listing.seller, "seller_country": listing.seller_country, "seller_region": listing.seller_region,
        "condition": listing.condition, "listing_kind": listing.listing_kind, "status": listing.status,
        "entity": entity_brief(listing),
        "price": {"asking": listing.asking_price, "currency": listing.currency,
                  "item_nok": listing.normalized_price_nok, "shipping_nok": listing.shipping_price_nok,
                  "import_buffer_nok": listing.import_buffer_nok or 0.0, "landed_nok": landed},
        "fair_value_nok": ev.fair_value_nok, "fair_value_low": ev.fair_value_low,
        "fair_value_high": ev.fair_value_high, "confidence": ev.fair_value_confidence,
        "discount_pct": ev.discount_pct,
        "discount_nok": round(ev.fair_value_nok - landed, 2) if ev.fair_value_nok else None,
        "score": ev.total_score, "raw_band": ev.recommendation, "level": ev.alert_level or ev.recommendation,
        "caps": (r.get("effective") or {}).get("caps", []), "warnings": r.get("warnings", []),
        "reasons": r.get("reasons", []), "notification": r.get("notification"),
        "trend_30d": (r.get("history") or {}).get("trend_30d"), "evaluated_at": ev.timestamp,
        "binder_fit": ev.binder_fit,
    }


def _latest_evals() -> Select:
    latest = (select(DealEvaluation.listing_id, func.max(DealEvaluation.id).label("ev_id"))
              .group_by(DealEvaluation.listing_id).subquery())
    return (select(Listing, DealEvaluation)
            .join(latest, latest.c.listing_id == Listing.id)
            .join(DealEvaluation, DealEvaluation.id == latest.c.ev_id))


# ---------------------------------------------------------------- deals
def deals(session: Session, levels: list[str] | None = None, source: str | None = None,
          seller_region: str | None = None, pokemon: str | None = None, set_code: str | None = None,
          min_landed: float | None = None, max_landed: float | None = None, min_discount: float | None = None,
          min_confidence: float | None = None, min_score: float | None = None, q: str | None = None,
          status: str = "active", sort: str = "score", limit: int = 100, offset: int = 0) -> dict[str, Any]:
    card, product = aliased(Card), aliased(Product)
    landed = func.coalesce(Listing.landed_cost_nok, Listing.total_price_nok)
    query = (_latest_evals().outerjoin(card, card.id == Listing.matched_card_id)
             .outerjoin(product, product.id == Listing.matched_product_id))
    if status != "all":
        query = query.where(Listing.status == status)
    if levels:
        query = query.where(LEVEL.in_(levels))
    if source:
        query = query.where(Listing.source == source)
    if seller_region:
        query = query.where(Listing.seller_region == seller_region)
    if pokemon:
        like = f"%{pokemon[:60]}%"
        query = query.where(or_(card.pokemon_name.ilike(like), card.name.ilike(like), product.name.ilike(like)))
    if set_code:
        query = query.where(or_(card.set_code == set_code, product.set_code == set_code))
    if min_landed is not None:
        query = query.where(landed >= min_landed)
    if max_landed is not None:
        query = query.where(landed <= max_landed)
    if min_discount is not None:
        query = query.where(DealEvaluation.discount_pct >= min_discount)
    if min_confidence is not None:
        query = query.where(DealEvaluation.fair_value_confidence >= min_confidence)
    if min_score is not None:
        query = query.where(DealEvaluation.total_score >= min_score)
    if q:
        query = query.where(Listing.title.ilike(f"%{q[:100]}%"))
    orders = {"score": DealEvaluation.total_score.desc(), "discount": DealEvaluation.discount_pct.desc(),
              "landed": landed.asc(), "newest": DealEvaluation.timestamp.desc()}
    order = orders.get(sort, orders["score"])
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.execute(query.order_by(order, Listing.id).limit(limit).offset(offset)).all()
    return {"total": total, "items": [deal_row(listing, ev) for listing, ev in rows]}


def _latest_snapshot(session: Session, etype: str, eid: int) -> PriceSnapshot | None:
    return session.scalar(select(PriceSnapshot).where(PriceSnapshot.entity_type == etype,
                                                      PriceSnapshot.entity_id == eid)
                          .order_by(PriceSnapshot.timestamp.desc()).limit(1))


def market_brief(snap: PriceSnapshot | None) -> dict[str, Any] | None:
    if snap is None:
        return None
    return {"low": snap.low_price, "cheapest3": snap.cheapest3_median, "cheapest5": snap.cheapest5_median,
            "cheapest10": snap.cheapest10_median, "broad_median": snap.median_price,
            "trimmed_median": snap.trimmed_median, "valid_listings": snap.listing_count,
            "excluded_listings": snap.excluded_count, "sellers": snap.seller_count, "dispersion": snap.dispersion,
            "has_expensive_tail": snap.has_expensive_tail, "observed_at": snap.timestamp}


def deal_detail(session: Session, listing_id: int) -> dict[str, Any] | None:
    row = session.execute(_latest_evals().where(Listing.id == listing_id)).first()
    if row is None:
        return None
    listing, ev = row
    out = deal_row(listing, ev)
    r = ev.reason_json or {}
    etype = EntityType.CARD if listing.matched_card_id else EntityType.PRODUCT
    eid = listing.matched_card_id or listing.matched_product_id
    out["market"] = market_brief(_latest_snapshot(session, etype, eid)) if eid else None
    out["history"] = r.get("history")
    out["fair_value_explanation"] = r.get("fair_value_explanation", [])
    out["fair_value_flags"] = r.get("fair_value_flags", [])
    out["components"] = r.get("components", {})
    out["weighted"] = r.get("weighted", {})
    out["modifiers"] = r.get("modifiers", {})
    out["item_discount_pct"] = r.get("item_discount_pct")
    out["grading"] = r.get("grading")
    out["sealed"] = r.get("sealed")
    out["match"] = {"status": listing.match_status, "confidence": listing.confidence}
    return out


# ---------------------------------------------------------------- portfolio / collection
def _holdings(session: Session) -> list[HoldingValue]:
    return value_holdings(session, lambda t, i: fair_value_nok(session, t, i))


def _kind(h: HoldingValue) -> str:
    if h.item.product_id:
        return "sealed"
    return "graded" if h.unit_graded_value is not None or h.item.grading_status == "graded" else "raw"


def holding_row(h: HoldingValue) -> dict[str, Any]:
    i = h.item
    return {
        "id": i.id, "kind": _kind(h), "entity": card_brief(i.card) or product_brief(i.product),
        "binder_type": i.binder_type, "quantity": i.quantity, "acquisition_price_nok": i.acquisition_price_nok,
        "acquisition_date": i.acquisition_date, "added_at": i.created_at, "condition": i.condition,
        "grading_status": i.grading_status, "grade_company": i.grade_company, "grade": i.psa_grade,
        "notes": i.notes, "unit_value_nok": h.unit_graded_value if h.unit_graded_value is not None
        else h.unit_raw_value, "value_priced": (h.unit_graded_value or h.unit_raw_value) is not None,
        "cost_nok": round(h.cost, 2), "value_nok": round(h.value, 2),
        "gain_nok": round(h.gain, 2) if (h.unit_graded_value or h.unit_raw_value) is not None else None,
        "gain_pct": round(h.gain_pct, 4) if h.gain_pct is not None and (h.unit_graded_value or h.unit_raw_value)
        is not None else None,
    }


def _priced(hs: list[HoldingValue]) -> list[HoldingValue]:
    return [h for h in hs if (h.unit_graded_value or h.unit_raw_value) is not None]


def _group(hs: list[HoldingValue]) -> dict[str, Any]:
    cost = sum(h.cost for h in hs)
    value = sum(h.value for h in hs)
    return {"count": sum(h.item.quantity for h in hs), "cost_nok": round(cost, 2), "value_nok": round(value, 2),
            "gain_nok": round(value - cost, 2), "gain_pct": round((value - cost) / cost, 4) if cost else None,
            "unpriced": sum(1 for h in hs if (h.unit_graded_value or h.unit_raw_value) is None)}


def portfolio_history(session: Session) -> dict[str, Any]:
    snaps = session.scalars(select(PortfolioSnapshot).order_by(PortfolioSnapshot.day)).all()
    points = [{"day": s.day, "cost_nok": s.total_cost_nok, "value_nok": round(s.raw_value_nok + s.graded_value_nok, 2),
               "gain_nok": round(s.raw_value_nok + s.graded_value_nok - s.total_cost_nok, 2), "by_binder": s.by_binder}
              for s in snaps if s.total_cost_nok > 0 or (s.raw_value_nok + s.graded_value_nok) > 0]
    return {"points": points, "ready": len(points) >= 2,
            "message": None if len(points) >= 2 else "History is being collected — one snapshot per day."}


def portfolio_overview(session: Session, holdings: list[HoldingValue] | None = None) -> dict[str, Any]:
    hs = holdings if holdings is not None else _holdings(session)
    summary = portfolio_summary(session, hs)
    groups = {k: _group([h for h in hs if _kind(h) == k]) for k in ("raw", "graded", "sealed")}
    priced = _priced(hs)
    return {
        "summary": summary,
        "by_kind": groups,
        "allocation": [{"kind": k, "value_nok": v["value_nok"], "cost_nok": v["cost_nok"], "count": v["count"]}
                       for k, v in groups.items() if v["count"]],
        "history": portfolio_history(session),
        "top_performers": [holding_row(h) for h in sorted(priced, key=lambda h: -(h.gain_pct or 0))[:5]
                           if (h.gain_pct or 0) > 0],
        "largest_positions": [holding_row(h) for h in sorted(priced, key=lambda h: -h.value)[:5]],
        "recent_additions": [holding_row(h) for h in sorted(hs, key=lambda h: h.item.created_at, reverse=True)[:5]],
    }


def portfolio_page(session: Session) -> dict[str, Any]:
    """Portfolio page: the overview plus every holding (one call, one valuation pass)."""
    hs = _holdings(session)
    return {**portfolio_overview(session, hs),
            "holdings": [holding_row(h) for h in sorted(hs, key=lambda h: -h.value)]}


def binder(session: Session, binder_type: str) -> dict[str, Any]:
    cfg = get_user_config().binders
    capacity = int((cfg.premium if binder_type == "premium" else cfg.regular).get("capacity_slots", 0))
    hs = [h for h in _holdings(session) if h.item.card_id and h.item.binder_type == binder_type]
    group = _group(hs)
    priced = _priced(hs)
    sets: dict[str, int] = defaultdict(int)
    for h in hs:
        sets[h.item.card.set_name or "Unknown set"] += h.item.quantity
    used = group["count"]
    return {
        "binder_type": binder_type, "capacity": capacity, "slots_used": used,
        "slots_free": max(capacity - used, 0), "over_capacity": used > capacity if capacity else False,
        "pct_complete": round(used / capacity, 4) if capacity else None,
        "summary": {**group, "avg_card_value_nok": round(group["value_nok"] / sum(h.item.quantity for h in priced), 2)
                    if priced else None},
        "sets": [{"set_name": k, "cards": v} for k, v in sorted(sets.items(), key=lambda kv: -kv[1])],
        "top_cards": [holding_row(h) for h in sorted(priced, key=lambda h: -h.value)[:5]],
        "recent_additions": [holding_row(h) for h in sorted(hs, key=lambda h: h.item.created_at, reverse=True)[:5]],
        "items": [holding_row(h) for h in sorted(hs, key=lambda h: -h.value)],
    }


def sealed(session: Session) -> dict[str, Any]:
    cfg = get_user_config()
    hs = [h for h in _holdings(session) if h.item.product_id]
    items = []
    for h in hs:
        p = h.item.product
        row = holding_row(h)
        packs = p.pack_count or None
        row["packs"] = packs * h.item.quantity if packs else None
        row["nok_per_pack_acquired"] = round(h.item.acquisition_price_nok / packs, 2) if packs else None
        row["nok_per_pack_now"] = round(h.unit_raw_value / packs, 2) if (packs and h.unit_raw_value) else None
        analysis = None
        if h.unit_raw_value:
            meta = cfg.sets.find(p.set_code) or cfg.sets.find(p.set_name)
            view = market_view(session, EntityType.PRODUCT, p.id)
            a = analyse_sealed(h.unit_raw_value, packs, _loose_pack_value(session, p.set_code), h.unit_raw_value,
                               p.release_date, meta.desirability if meta else cfg.sets.default_desirability,
                               _top_chase_value(session, p.set_code), view.history.trend_30d)
            analysis = {"rip_score": a.rip_score, "hold_score": a.sealed_investment_score,
                        "sealed_premium": a.sealed_premium, "loose_pack_value_nok": a.loose_pack_value_nok,
                        "product_age_years": a.product_age_years, "notes": a.notes}
        row["analysis"] = analysis
        items.append(row)
    group = _group(hs)
    return {"summary": {**group, "products": len(hs),
                        "total_packs": sum(r["packs"] or 0 for r in items)}, "items": items}


# ---------------------------------------------------------------- grading
def _refs(session: Session, card_id: int) -> dict[float, dict[str, Any]]:
    out: dict[float, dict[str, Any]] = {}
    for r in session.scalars(select(GradedPriceReference).where(GradedPriceReference.card_id == card_id,
                                                               GradedPriceReference.grade_company == "PSA")
                             .order_by(GradedPriceReference.updated_at.desc())).all():
        out.setdefault(r.grade, {"price_nok": r.price_nok, "source": r.source, "updated_at": r.updated_at,
                                 "confidence": r.confidence})
    return out


def grading(session: Session) -> dict[str, Any]:
    gcfg = get_user_config().grading
    groups: dict[str, list[dict[str, Any]]] = {"candidates": [], "submitted": [], "at_grader": [], "returned": []}
    for h in (h for h in _holdings(session) if h.item.card_id):
        i = h.item
        refs = _refs(session, i.card_id)
        psa9, psa10 = refs.get(9.0), refs.get(10.0)
        raw = h.unit_raw_value
        econ = grading_economics(raw, psa9 and psa9["price_nok"], psa10 and psa10["price_nok"], gcfg)
        row = holding_row(h) | {
            "raw_value_nok": raw, "psa9": psa9, "psa10": psa10, "grading_cost_nok": gcfg.estimated_grading_cost_nok,
            "psa9_net_nok": round(psa9["price_nok"] - raw - gcfg.estimated_grading_cost_nok, 2)
            if (psa9 and raw) else None,
            "psa10_net_nok": round(psa10["price_nok"] - raw - gcfg.estimated_grading_cost_nok, 2)
            if (psa10 and raw) else None,
            "upside_psa9": econ.upside_psa9, "upside_psa10": econ.upside_psa10, "grading_label": econ.label,
            "flags": econ.flags,
            "missing": [m for m, ok in (("raw value", raw), ("PSA 9 reference", psa9), ("PSA 10 reference", psa10))
                        if not ok],
        }
        status = i.grading_status or "raw"
        key = {"raw": "candidates", "submitted": "submitted", "at_grader": "at_grader", "graded": "returned"}.get(
            status, "candidates")
        groups[key].append(row)
    groups["candidates"].sort(key=lambda r: (r["upside_psa10"] is None, -(r["upside_psa10"] or 0)))
    return {"grading_cost_nok": gcfg.estimated_grading_cost_nok, **groups,
            "counts": {k: len(v) for k, v in groups.items()}}


# ---------------------------------------------------------------- watchlist
def _best_listing(session: Session, etype: str, eid: int) -> tuple[Listing, DealEvaluation] | None:
    col = Listing.matched_card_id if etype == EntityType.CARD else Listing.matched_product_id
    landed = func.coalesce(Listing.landed_cost_nok, Listing.total_price_nok)
    row = session.execute(_latest_evals().where(col == eid, Listing.status == "active")
                          .order_by(landed.asc()).limit(1)).first()
    return (row[0], row[1]) if row else None


def _daily_c5(session: Session, etype: str, eid: int, days: int) -> list[dict[str, Any]]:
    rows = session.scalars(select(PriceDaily).where(
        PriceDaily.entity_type == etype, PriceDaily.entity_id == eid,
        PriceDaily.day >= utc_today() - timedelta(days=days)).order_by(PriceDaily.day)).all()
    return [{"day": r.day, "cheapest5": r.cheapest5_median, "low": r.low_price} for r in rows]


def watchlist(session: Session) -> dict[str, Any]:
    items = []
    for w in session.scalars(select(WatchlistItem).order_by(WatchlistItem.id)).all():
        entity = card_brief(session.get(Card, w.entity_id)) if w.target_type == "card" \
            else product_brief(session.get(Product, w.entity_id))
        view = market_view(session, w.target_type, w.entity_id)
        best = _best_listing(session, w.target_type, w.entity_id)
        best_row = deal_row(*best) if best else None
        fv = view.fair_value.fair_value_nok
        landed = best_row["price"]["landed_nok"] if best_row else None
        items.append({
            "id": w.id, "entity": entity, "target_type": w.target_type, "priority": w.priority,
            "enabled": w.enabled, "notes": w.notes, "target_buy_price_nok": w.target_buy_price,
            "fair_value_nok": fv, "confidence": view.fair_value.confidence,
            "fair_value_flags": view.fair_value.flags,
            "market": {"low": view.current.low, "cheapest5": view.current.cheapest5_median,
                       "valid_listings": view.current.listing_count},
            "trend_30d": view.history.trend_30d, "history_days": view.history.days_30d,
            "history": _daily_c5(session, w.target_type, w.entity_id, 30),
            "best_listing": best_row,
            "best_discount_pct": round((fv - landed) / fv, 4) if (fv and landed) else None,
            "below_target": bool(w.target_buy_price and landed and landed <= w.target_buy_price),
        })
    return {"items": items}


# ---------------------------------------------------------------- market
def market(session: Session, window_days: int = 30, min_value_nok: float = 100) -> dict[str, Any]:
    since = utc_today() - timedelta(days=window_days)
    daily = session.scalars(select(PriceDaily).where(PriceDaily.day >= since).order_by(PriceDaily.day)).all()
    series: dict[tuple[str, int], list[PriceDaily]] = defaultdict(list)
    for r in daily:
        if r.cheapest5_median:
            series[(r.entity_type, r.entity_id)].append(r)
    movers = []
    for (etype, eid), rows in series.items():
        if len(rows) < 2 or rows[-1].cheapest5_median < min_value_nok:
            continue
        first, last = rows[0].cheapest5_median, rows[-1].cheapest5_median
        movers.append({"entity_type": etype, "entity_id": eid, "from_nok": first, "to_nok": last,
                       "change_pct": round(last / first - 1, 4), "from_day": rows[0].day, "to_day": rows[-1].day,
                       "days": len(rows)})
    _attach_entities(session, movers)
    latest_ids = select(func.max(PriceSnapshot.id)).group_by(PriceSnapshot.entity_type, PriceSnapshot.entity_id)
    latest = session.scalars(select(PriceSnapshot).where(PriceSnapshot.id.in_(latest_ids))).all()
    liquid = [{"entity_type": s.entity_type, "entity_id": s.entity_id, "valid_listings": s.listing_count,
               "cheapest5": s.cheapest5_median, "low": s.low_price}
              for s in sorted((s for s in latest if (s.cheapest5_median or 0) >= min_value_nok),
                              key=lambda s: -s.listing_count)[:10]]
    _attach_entities(session, liquid)
    days_collected = session.scalar(select(func.count(func.distinct(PriceDaily.day)))) or 0
    per_entity_days = select(func.count(PriceDaily.id).label("n")).group_by(PriceDaily.entity_type,
                                                                            PriceDaily.entity_id).subquery()
    return {
        "coverage": {
            "observations": session.scalar(select(func.count(PriceSnapshot.id))) or 0,
            "daily_rows": session.scalar(select(func.count(PriceDaily.id))) or 0,
            "tracked_entities": len(latest),
            "tracked_cards": sum(1 for s in latest if s.entity_type == EntityType.CARD),
            "tracked_products": sum(1 for s in latest if s.entity_type == EntityType.PRODUCT),
            "days_collected": days_collected,
            "first_day": session.scalar(select(func.min(PriceDaily.day))),
            "last_day": session.scalar(select(func.max(PriceDaily.day))),
            "first_observation": session.scalar(select(func.min(PriceSnapshot.timestamp))),
            "last_observation": session.scalar(select(func.max(PriceSnapshot.timestamp))),
            "entities_with_7_days": session.scalar(select(func.count()).select_from(per_entity_days)
                                                   .where(per_entity_days.c.n >= 7)) or 0,
            "min_value_nok": min_value_nok,
        },
        "movers_ready": bool(movers),
        "gainers": sorted((m for m in movers if m["change_pct"] > 0), key=lambda m: -m["change_pct"])[:10],
        "decliners": sorted((m for m in movers if m["change_pct"] < 0), key=lambda m: m["change_pct"])[:10],
        "most_liquid": liquid,
        # Only fair values trustworthy enough to alert on (same minimum as the alert policy); a thin
        # market with an absurd placeholder ask must not be showcased as a 99 % "discount".
        "strongest_discounts": deals(session, min_discount=0.0, sort="discount", limit=10,
                                     min_confidence=get_user_config().alerts.min_fair_value_confidence)["items"],
    }


def _attach_entities(session: Session, rows: list[dict[str, Any]]) -> None:
    cards = {c.id: c for c in session.scalars(select(Card).where(
        Card.id.in_([r["entity_id"] for r in rows if r["entity_type"] == EntityType.CARD]))).all()}
    products = {p.id: p for p in session.scalars(select(Product).where(
        Product.id.in_([r["entity_id"] for r in rows if r["entity_type"] == EntityType.PRODUCT]))).all()}
    for r in rows:
        r["entity"] = card_brief(cards.get(r["entity_id"])) if r["entity_type"] == EntityType.CARD \
            else product_brief(products.get(r["entity_id"]))


def market_series(session: Session, etype: str, eid: int, days: int = 90) -> dict[str, Any] | None:
    entity = (card_brief(session.get(Card, eid)) if etype == EntityType.CARD
              else product_brief(session.get(Product, eid)))
    if entity is None:
        return None
    since = utc_today() - timedelta(days=days)
    daily = session.scalars(select(PriceDaily).where(PriceDaily.entity_type == etype, PriceDaily.entity_id == eid,
                                                     PriceDaily.day >= since).order_by(PriceDaily.day)).all()
    # Fair value history = what the scorer actually used: daily median of stored evaluations.
    col = Listing.matched_card_id if etype == EntityType.CARD else Listing.matched_product_id
    evs = session.execute(select(DealEvaluation.timestamp, DealEvaluation.fair_value_nok)
                          .join(Listing, Listing.id == DealEvaluation.listing_id)
                          .where(col == eid, DealEvaluation.fair_value_nok.is_not(None),
                                 DealEvaluation.timestamp >= datetime.combine(since, datetime.min.time()))).all()
    fv_by_day: dict[date, list[float]] = defaultdict(list)
    for ts, fv in evs:
        fv_by_day[ts.date()].append(fv)
    days_all = sorted({r.day for r in daily} | set(fv_by_day))
    by_day = {r.day: r for r in daily}
    points = [{"day": d, "low": by_day[d].low_price if d in by_day else None,
               "cheapest5": by_day[d].cheapest5_median if d in by_day else None,
               "fair_value": round(statistics.median(fv_by_day[d]), 2) if d in fv_by_day else None}
              for d in days_all]
    raw = session.scalars(select(PriceSnapshot).where(
        PriceSnapshot.entity_type == etype, PriceSnapshot.entity_id == eid,
        PriceSnapshot.timestamp >= utcnow() - timedelta(days=7)).order_by(PriceSnapshot.timestamp)).all()
    view = market_view(session, etype, eid)
    return {"entity": entity, "daily": points, "history_ready": len(daily) >= 2,
            "intraday": [{"timestamp": s.timestamp, "low": s.low_price, "cheapest5": s.cheapest5_median,
                          "valid_listings": s.listing_count} for s in raw],
            "current": market_brief(_latest_snapshot(session, etype, eid)),
            "fair_value": {"value_nok": view.fair_value.fair_value_nok, "low": view.fair_value.fair_value_low,
                           "high": view.fair_value.fair_value_high, "confidence": view.fair_value.confidence,
                           "flags": view.fair_value.flags, "explanation": view.fair_value.explanation},
            "history": view.history.__dict__}


# ---------------------------------------------------------------- alerts
def alerts(session: Session, days: int = 7) -> dict[str, Any]:
    now = utcnow()
    since = now - timedelta(days=days)
    start_today = datetime.combine(now.date(), datetime.min.time())
    rows = session.execute(
        select(Alert, DealEvaluation, Listing)
        .outerjoin(DealEvaluation, DealEvaluation.id == Alert.deal_evaluation_id)
        .outerjoin(Listing, Listing.id == Alert.listing_id)
        .where(Alert.sent_at >= since).order_by(Alert.sent_at.desc()).limit(500)).all()
    sent = []
    for a, ev, listing in rows:
        sent.append({
            "id": a.id, "kind": a.kind, "sent_at": a.sent_at, "level": a.severity, "dry_run": a.dry_run,
            "delivered": a.telegram_message_id is not None, "telegram_message_id": a.telegram_message_id,
            "price_nok": a.price_nok, "fair_value_nok": ev.fair_value_nok if ev else None,
            "discount_pct": ev.discount_pct if ev else None, "listing_id": a.listing_id,
            "url": listing.url if listing else None, "source": listing.source if listing else None,
            "entity": entity_brief(listing) if listing else None,
            "title": listing.title if listing else None, "message": a.message if a.kind != "deal" else None,
        })
    deal_alerts = [s for s in sent if s["kind"] == "deal"]
    blocked = []
    evs = session.execute(
        select(DealEvaluation, Listing).join(Listing, Listing.id == DealEvaluation.listing_id)
        .where(DealEvaluation.timestamp >= since, LEVEL.in_(GOOD_PLUS))
        .order_by(DealEvaluation.timestamp.desc()).limit(500)).all()
    for ev, listing in evs:
        n = (ev.reason_json or {}).get("notification")
        if not n or n.get("notify"):
            continue
        reasons = n.get("blocked_by", [])
        blocked.append({
            "evaluation_id": ev.id, "timestamp": ev.timestamp, "listing_id": listing.id, "url": listing.url,
            "source": listing.source, "entity": entity_brief(listing), "title": listing.title,
            "level": ev.alert_level or ev.recommendation, "price_nok": ev.price_nok,
            "fair_value_nok": ev.fair_value_nok, "discount_pct": ev.discount_pct, "blocked_by": reasons,
            "cooldown": any("already alerted" in b or "same card" in b for b in reasons),
            "region_blocked": any(b.startswith("seller_region_not_allowed") for b in reasons),
        })

    def count(pred) -> int:
        return sum(1 for s in deal_alerts if pred(s))

    return {
        "summary": {
            "today": count(lambda s: s["sent_at"] >= start_today),
            "window": len(deal_alerts), "window_days": days,
            "by_level": {lv: count(lambda s, lv=lv: s["level"] == lv) for lv in GOOD_PLUS},
            "live": count(lambda s: not s["dry_run"]), "dry_run": count(lambda s: s["dry_run"]),
            "blocked": len(blocked), "health_alerts": sum(1 for s in sent if s["kind"] == "health"),
        },
        "alerts": sent, "blocked": blocked[:200],
    }


# ---------------------------------------------------------------- overview
def overview(session: Session) -> dict[str, Any]:
    from app.api.routes.sources import source_health

    now = utcnow()
    start_today = datetime.combine(now.date(), datetime.min.time())
    active_good = select(func.count()).select_from(
        _latest_evals().where(Listing.status == "active", LEVEL.in_(GOOD_PLUS)).subquery())
    today_alerts = session.execute(select(Alert.dry_run, func.count(Alert.id)).where(
        Alert.kind == "deal", Alert.sent_at >= start_today).group_by(Alert.dry_run)).all()
    alerts_today = {"live": 0, "dry_run": 0}
    for dry, n in today_alerts:
        alerts_today["dry_run" if dry else "live"] += n
    best = deals(session, levels=list(GOOD_PLUS), limit=6)["items"]
    near = [] if len(best) >= 3 else [
        d for d in deals(session, levels=["WATCH"], min_discount=0.05, limit=4)["items"]]
    health = [h for h in source_health(session) if h["kind"] == "scheduled" and h["enabled"]]
    return {
        "portfolio": portfolio_overview(session),
        "kpis": {
            "active_deals": session.scalar(active_good) or 0,
            "watchlist_count": session.scalar(select(func.count(WatchlistItem.id)).where(
                WatchlistItem.enabled.is_(True))) or 0,
            "alerts_today": {**alerts_today, "total": alerts_today["live"] + alerts_today["dry_run"]},
            "active_listings": session.scalar(select(func.count(Listing.id)).where(Listing.status == "active")) or 0,
        },
        "best_deals": best,
        "near_deals": near,
        "system": [{"source": h["source"], "healthy": h["healthy"], "mode": h["mode"],
                    "last_success": h["worker"]["last_successful_scan"], "worker": h["worker"],
                    "lock": h["scan_lock"]} for h in health],
    }


# ---------------------------------------------------------------- system
def system(session: Session) -> dict[str, Any]:
    import os
    from pathlib import Path

    from sqlalchemy import text

    from app.api.routes.health import ready
    from app.api.routes.sources import source_health
    from app.core.config import get_settings
    from app.db.models import CollectorRun, ExchangeRate

    class _Resp:  # ready() sets status_code on a Response; we only want its checks
        status_code = 200

    checks = ready(_Resp())["checks"]
    s = get_settings()
    dialect = session.get_bind().dialect.name
    db_size = None
    if dialect == "postgresql":
        db_size = session.scalar(text("SELECT pg_database_size(current_database())"))
    migration = None
    try:
        migration = session.scalar(text("SELECT version_num FROM alembic_version"))
    except Exception:  # noqa: BLE001 - diagnostics only
        session.rollback()
    sources = source_health(session)
    ct = next((h for h in sources if h["source"] == "cardtrader"), None)
    since = utcnow() - timedelta(hours=24)
    runs = session.scalars(select(CollectorRun).where(CollectorRun.started_at >= since)
                           .order_by(CollectorRun.started_at.desc())).all()
    last_alert = session.scalar(select(func.max(Alert.sent_at)).where(Alert.kind == "deal"))
    fx = session.scalar(select(ExchangeRate).where(ExchangeRate.currency == "EUR")
                        .order_by(ExchangeRate.day.desc()).limit(1))

    backups: dict[str, Any] = {"configured": False}
    bdir = Path(os.environ.get("BACKUP_DIR", "")) if os.environ.get("BACKUP_DIR") else None
    if bdir and bdir.is_dir():
        files = sorted(bdir.glob("*/*.dump"), key=lambda p: p.stat().st_mtime, reverse=True)
        latest = files[0] if files else None
        backups = {"configured": True, "count_daily": len(list(bdir.glob("daily/*.dump"))),
                   "count_weekly": len(list(bdir.glob("weekly/*.dump"))),
                   "latest_file": latest.name if latest else None,
                   "latest_at": datetime.fromtimestamp(latest.stat().st_mtime, UTC).replace(tzinfo=None)
                   if latest else None,
                   "latest_size_bytes": latest.stat().st_size if latest else None}

    return {
        # Healthy only if the core checks pass AND an enabled scanner is actually scheduled (a stopped
        # worker is not "operational" even though nothing is overdue).
        "overall_ok": all(v == "ok" for k, v in checks.items() if k in ("database", "migrations", "config"))
        and bool(ct and (not ct["enabled"] or (ct["worker"]["worker_scheduled"]
                                                and not ct["worker"]["next_scan_overdue"]))),
        "database": {"ok": checks.get("database") == "ok", "migrations": checks.get("migrations"),
                     "dialect": dialect, "migration_version": migration, "size_bytes": db_size},
        "worker": None if ct is None else {
            **ct["worker"], "lock": ct["scan_lock"], "scans_24h": len([r for r in runs if r.source == "cardtrader"]),
            "errors_24h": len([r for r in runs if r.source == "cardtrader" and not r.success]),
            "error_rate_24h": ct["error_rate_24h"], "last_error": ct["last_error"],
            "last_duration_ms": ct["last_duration_ms"], "interval_minutes": ct["interval_minutes"]},
        "sources": sources,
        "telegram": {"mode": checks.get("telegram_mode"),
                     "configured": bool(s.telegram_bot_token and s.telegram_bot_token.get_secret_value()
                                        and s.telegram_chat_id),
                     "last_deal_alert_at": last_alert},
        "cardtrader": {"mode": checks.get("cardtrader_mode")},
        "fx": {"eur_nok": fx.nok_per_unit if fx else None, "day": fx.day if fx else None},
        "backups": backups,
        "diagnostics": {"ready_checks": checks, "environment": s.environment,
                        "recent_runs": [{"source": r.source, "started_at": r.started_at, "success": r.success,
                                         "duration_ms": r.duration_ms, "error": r.error} for r in runs[:10]]},
    }

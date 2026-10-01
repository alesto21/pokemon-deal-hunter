"""Plain-dict serialisers for API responses."""

from __future__ import annotations

from typing import Any

from app.db.models import Card, DealEvaluation, Listing, PortfolioItem, Product, WatchlistItem


def card_out(c: Card | None) -> dict[str, Any] | None:
    if c is None:
        return None
    return {"id": c.id, "name": c.name, "set_name": c.set_name, "set_code": c.set_code,
            "card_number": c.card_number, "rarity": c.rarity, "language": c.language,
            "pokemon_name": c.pokemon_name, "release_date": c.release_date, "image_url": c.image_url,
            "is_promo": c.is_promo, "source_ids": c.source_ids}


def product_out(p: Product | None) -> dict[str, Any] | None:
    if p is None:
        return None
    return {"id": p.id, "name": p.name, "product_type": p.product_type, "set_name": p.set_name,
            "set_code": p.set_code, "pack_count": p.pack_count, "language": p.language,
            "release_date": p.release_date, "image_url": p.image_url, "source_ids": p.source_ids}


def entity_label(listing: Listing) -> str | None:
    if listing.card:
        return f"{listing.card.name} {listing.card.card_number or ''}".strip()
    if listing.product:
        return listing.product.name
    return None


def evaluation_out(ev: DealEvaluation | None) -> dict[str, Any] | None:
    if ev is None:
        return None
    r = ev.reason_json or {}
    return {"id": ev.id, "timestamp": ev.timestamp, "price_nok": ev.price_nok,
            "fair_value_nok": ev.fair_value_nok, "fair_value_low": ev.fair_value_low,
            "fair_value_high": ev.fair_value_high, "fair_value_confidence": ev.fair_value_confidence,
            "discount_pct": ev.discount_pct, "total_score": ev.total_score, "recommendation": ev.recommendation,
            "raw_band": ev.recommendation, "alert_level": ev.alert_level or ev.recommendation,
            "caps": (r.get("effective") or {}).get("caps", []),
            "binder_fit": ev.binder_fit,
            "scores": {"liquidity": ev.liquidity_score, "popularity": ev.popularity_score, "set": ev.set_score,
                       "trend": ev.trend_score, "grading": ev.grading_score, "scarcity": ev.scarcity_score,
                       "portfolio_points": ev.portfolio_score, "seller_confidence": ev.seller_confidence_score},
            "trend_30d": (r.get("history") or {}).get("trend_30d"),
            "median_30d": (r.get("history") or {}).get("median_30d"),
            "reasons": r.get("reasons", []), "warnings": r.get("warnings", []),
            "notification": r.get("notification"), "details": r}


def listing_out(listing: Listing, ev: DealEvaluation | None = None) -> dict[str, Any]:
    return {"id": listing.id, "source": listing.source, "external_id": listing.external_id, "url": listing.url,
            "title": listing.title, "seller": listing.seller, "seller_rating": listing.seller_rating,
            "condition": listing.condition, "language": listing.language, "listing_kind": listing.listing_kind,
            "is_graded": listing.is_graded, "grade_company": listing.grade_company, "grade": listing.grade,
            "quantity": listing.quantity, "asking_price": listing.asking_price, "currency": listing.currency,
            "normalized_price_nok": listing.normalized_price_nok, "shipping_price_nok": listing.shipping_price_nok,
            "total_price_nok": listing.total_price_nok, "first_seen": listing.first_seen,
            "seller_country": listing.seller_country, "seller_region": listing.seller_region,
            "import_buffer_nok": listing.import_buffer_nok or 0.0, "landed_cost_nok": listing.scoring_price_nok,
            "fees_nok": listing.fees_nok or 0.0, "shipping_basis": listing.shipping_basis,
            "fees_basis": listing.fees_basis, "landed_cost_confidence": listing.landed_cost_confidence,
            "purchase_route": listing.purchase_route, "pickup_required": listing.pickup_required,
            "location": listing.location, "seller_type": listing.seller_type,
            "published_at": listing.published_at, "capture_method": listing.capture_method,
            "safety_flags": listing.safety_flags or [], "extracted": listing.extracted or {},
            "last_seen": listing.last_seen, "status": listing.status,
            "matched_card_id": listing.matched_card_id, "matched_product_id": listing.matched_product_id,
            "entity_label": entity_label(listing), "confidence": listing.confidence,
            "match_status": listing.match_status, "match_candidates": listing.match_candidates,
            "image_urls": listing.image_urls, "evaluation": evaluation_out(ev)}


def portfolio_item_out(i: PortfolioItem) -> dict[str, Any]:
    return {"id": i.id, "card_id": i.card_id, "product_id": i.product_id, "card": card_out(i.card),
            "product": product_out(i.product), "quantity": i.quantity,
            "acquisition_price_nok": i.acquisition_price_nok, "acquisition_date": i.acquisition_date,
            "binder_type": i.binder_type, "condition": i.condition, "grading_status": i.grading_status,
            "grade_company": i.grade_company, "psa_grade": i.psa_grade, "notes": i.notes}


def watchlist_out(w: WatchlistItem, label: str | None, fair_value: float | None) -> dict[str, Any]:
    return {"id": w.id, "entity_id": w.entity_id, "target_type": w.target_type, "label": label,
            "target_buy_price": w.target_buy_price, "priority": w.priority, "enabled": w.enabled,
            "notes": w.notes, "fair_value_nok": fair_value}

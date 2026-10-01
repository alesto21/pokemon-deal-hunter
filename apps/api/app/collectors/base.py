"""Collector primitives: a normalised raw listing and the shared upsert logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_user_config
from app.core.logging import get_logger
from app.core.security import sanitize_text
from app.db.base import utcnow
from app.db.models import EntityType, Listing, ListingStatus, MatchStatus
from app.matching.matcher import match_listing
from app.pricing.fx import FxRates
from app.pricing.landed_cost import ShippingQuote, cardtrader_landed_cost, estimate_landed_cost

log = get_logger(__name__)


@dataclass
class RawListing:
    source: str
    external_id: str
    title: str
    asking_price: float
    currency: str
    url: str | None = None
    description: str | None = None
    seller: str | None = None
    seller_rating: float | None = None
    condition: str | None = None
    language: str | None = None
    quantity: int = 1
    shipping_nok: float | None = None      # None → regional estimate from sources.yaml
    shipping_known: bool = False           # True when shipping_nok was stated by seller/user (exact)
    seller_country: str | None = None      # ISO-2; None/unknown → region "other"
    seller_external_id: str | None = None  # source's seller id (seller-basket grouping)
    via_hub: bool | None = None            # cardtrader: seller ships via CardTrader Zero
    shipping_basis: str | None = None      # explicit basis: exact | estimated | included | pickup
    location: str | None = None
    seller_type: str | None = None         # private | business
    published_at: datetime | None = None
    pickup_required: bool = False
    capture_method: str | None = None      # manual | csv | capture
    is_graded: bool = False
    grade_company: str | None = None
    grade: float | None = None
    listing_kind: str | None = None
    image_urls: list[str] = field(default_factory=list)
    # Set when the source already tells us the exact entity (e.g. CardTrader blueprint).
    known_entity: tuple[str, int] | None = None


@dataclass
class CollectorResult:
    fetched: int = 0
    matched: int = 0
    listing_ids: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class Collector(Protocol):
    name: str

    def collect(self, session: Session) -> CollectorResult: ...


def find_quote(session: Session, source: str, seller_external_id: str | None, seller: str | None,
               route: str) -> ShippingQuote | None:
    """Observed checkout quote for this seller and route (exact shipping), if one was recorded."""
    from app.db.models import SellerShippingQuote

    if not (seller_external_id or seller):
        return None
    q = select(SellerShippingQuote).where(SellerShippingQuote.source == source, SellerShippingQuote.route == route)
    q = q.where(SellerShippingQuote.seller_external_id == seller_external_id) if seller_external_id \
        else q.where(SellerShippingQuote.seller == seller)
    row = session.scalar(q.order_by(SellerShippingQuote.observed_at.desc()).limit(1))
    if row is None and seller_external_id and seller:  # quote recorded by username only
        row = session.scalar(select(SellerShippingQuote).where(
            SellerShippingQuote.source == source, SellerShippingQuote.route == route,
            SellerShippingQuote.seller == seller).order_by(SellerShippingQuote.observed_at.desc()).limit(1))
    return ShippingQuote(row.shipment_nok, row.fees_nok, row.capacity_items) if row else None


def upsert_listing(session: Session, raw: RawListing, fx: FxRates) -> Listing:
    """Insert or update a listing, normalise its price to NOK and (re)match it if needed."""
    price_nok = fx.to_nok(raw.asking_price, raw.currency)
    sources = get_user_config().sources
    if raw.source == "cardtrader":
        route = "zero" if raw.via_hub else "direct"
        cost = cardtrader_landed_cost(price_nok, raw.seller_country, bool(raw.via_hub), sources,
                                      find_quote(session, raw.source, raw.seller_external_id, raw.seller, route))
    else:
        cost = estimate_landed_cost(price_nok, raw.seller_country, sources, raw.shipping_nok, raw.shipping_known,
                                    raw.shipping_basis)
    total = round(price_nok + cost.shipping_nok, 2)
    listing = session.scalar(
        select(Listing).where(Listing.source == raw.source, Listing.external_id == raw.external_id)
    )
    now = utcnow()
    if listing is None:
        listing = Listing(source=raw.source, external_id=raw.external_id, first_seen=now,
                          title=sanitize_text(raw.title, 500) or "(untitled)",
                          asking_price=raw.asking_price, normalized_price_nok=price_nok,
                          total_price_nok=total, image_urls=[])
        session.add(listing)
    elif abs(listing.total_price_nok - total) > 0.5:
        listing.previous_total_price_nok = listing.total_price_nok  # price history of item + shipping
    listing.title = sanitize_text(raw.title, 500) or listing.title
    listing.url = raw.url
    listing.description = sanitize_text(raw.description, 4000)
    listing.seller = sanitize_text(raw.seller, 200)
    listing.seller_rating = raw.seller_rating
    listing.condition = sanitize_text(raw.condition, 64)
    listing.language = raw.language
    listing.quantity = raw.quantity
    listing.asking_price = raw.asking_price
    listing.currency = raw.currency.upper()
    listing.normalized_price_nok = price_nok
    listing.shipping_price_nok = cost.shipping_nok
    listing.total_price_nok = total
    listing.seller_country = cost.seller_country
    listing.seller_region = cost.seller_region
    listing.import_buffer_nok = cost.import_buffer_nok
    listing.fees_nok = cost.fees_nok
    listing.shipping_basis = cost.shipping_basis
    listing.fees_basis = cost.fees_basis
    listing.landed_cost_confidence = cost.confidence
    listing.purchase_route = cost.route
    listing.seller_external_id = raw.seller_external_id
    listing.pickup_required = raw.pickup_required
    for attr in ("location", "seller_type", "published_at", "capture_method"):
        if getattr(raw, attr) is not None:
            setattr(listing, attr, getattr(raw, attr))
    listing.landed_cost_nok = cost.landed_cost_nok
    listing.is_graded = raw.is_graded
    listing.grade_company = raw.grade_company
    listing.grade = raw.grade
    listing.image_urls = raw.image_urls[:20]
    listing.last_seen = now
    if listing.status == ListingStatus.GONE:
        listing.status = ListingStatus.ACTIVE

    if raw.known_entity:
        etype, eid = raw.known_entity
        listing.matched_card_id = eid if etype == EntityType.CARD else None
        listing.matched_product_id = eid if etype == EntityType.PRODUCT else None
        listing.confidence, listing.match_status = 1.0, MatchStatus.AUTO
        listing.listing_kind = raw.listing_kind or ("sealed" if etype == EntityType.PRODUCT else "single")
    elif listing.match_status not in (MatchStatus.MANUAL, MatchStatus.REJECTED):
        _apply_match(session, listing, raw)
    session.flush()
    return listing


def _apply_match(session: Session, listing: Listing, raw: RawListing) -> None:
    result = match_listing(session, listing.title, get_user_config().sets)
    parsed = result.parsed
    listing.listing_kind = raw.listing_kind or (
        "lot" if parsed.is_lot else "graded" if (raw.is_graded or parsed.grade_company)
        else "sealed" if parsed.product_type else "single")
    if parsed.grade_company and not listing.is_graded:
        listing.is_graded, listing.grade_company, listing.grade = True, parsed.grade_company, parsed.grade
    if not listing.condition and parsed.condition:
        listing.condition = parsed.condition
    if not listing.language:
        listing.language = parsed.language
    listing.confidence = result.confidence
    listing.match_status = result.status
    listing.match_candidates = result.candidates_json()
    listing.matched_card_id = result.entity_id if result.entity_type == EntityType.CARD else None
    listing.matched_product_id = result.entity_id if result.entity_type == EntityType.PRODUCT else None
    log.info("listing_matched", source=listing.source, listing_id=listing.external_id,
             match_id=result.entity_id, confidence=result.confidence, action=result.status)

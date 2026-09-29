"""Collector primitives: a normalised raw listing and the shared upsert logic."""

from __future__ import annotations

from dataclasses import dataclass, field
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
    shipping_nok: float = 0.0
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


def upsert_listing(session: Session, raw: RawListing, fx: FxRates) -> Listing:
    """Insert or update a listing, normalise its price to NOK and (re)match it if needed."""
    price_nok = fx.to_nok(raw.asking_price, raw.currency)
    total = round(price_nok + (raw.shipping_nok or 0), 2)
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
        listing.previous_total_price_nok = listing.total_price_nok
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
    listing.shipping_price_nok = raw.shipping_nok
    listing.total_price_nok = total
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

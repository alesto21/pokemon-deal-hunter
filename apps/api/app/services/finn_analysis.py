"""FINN listing analysis after ingestion: lot detection + conservative lot identification, and
"verify listing"-style safety labels. Deterministic; no network access; nothing is guessed.

Lot identification rules (v1, text only):
* a card is IDENTIFIED only if set + number/printed total match exactly one catalogue card AND
  that card's Pokémon is named in the text;
* a sealed product is identified only if its type + set match exactly one catalogue product;
* everything else is counted as unidentified. PSA mentions are recorded, not valued.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.collectors.finn_text import LotDetails, extract_lot_details
from app.core.config import UserConfig, get_user_config
from app.db.base import utcnow
from app.db.models import Card, Listing, ListingStatus, Lot, LotItem, MatchStatus, Product
from app.matching.normalize import fold, split_card_number

LOW_INFO_CHARS = 40


def pokemon_names(session: Session, cfg: UserConfig) -> list[str]:
    names = {n for (n,) in session.execute(select(Card.pokemon_name).distinct()) if n}
    for tier in cfg.pokemon.popularity_tiers.values():
        names.update(tier.names)
    return sorted(names)


def _identify_card(session: Session, number: str, details: LotDetails, text: str, cfg: UserConfig) -> Card | None:
    num, total = split_card_number(number)
    if not (num and total and total.isdigit()):
        return None
    set_codes = [s.code for s in cfg.sets.sets if s.printed_total == int(total)]
    candidates = [c for c in session.scalars(select(Card).where(Card.set_code.in_(set_codes))).all()
                  if split_card_number(c.card_number) == (num, total)]
    if len(candidates) != 1:
        return None
    card = candidates[0]
    name = fold(card.pokemon_name or card.name)
    return card if name and name in fold(text) else None


def _identify_products(session: Session, details: LotDetails) -> list[Product]:
    found = []
    for ptype in details.sealed_products:
        for code in details.sets:
            rows = session.scalars(select(Product).where(Product.product_type == ptype,
                                                         Product.set_code == code)).all()
            if len(rows) == 1:
                found.append(rows[0])
    return found


def analyse_lot(session: Session, listing: Listing, details: LotDetails) -> Lot:
    """Create/refresh the listing's Lot from text. Manual lot items are never touched."""
    cfg = get_user_config()
    text = f"{listing.title}\n{listing.description or ''}"
    lot = session.scalar(select(Lot).where(Lot.listing_id == listing.id))
    if lot is None:
        lot = Lot(listing_id=listing.id, images=[])
        session.add(lot)
        session.flush()
    for item in [i for i in lot.items if i.origin == "auto"]:
        lot.items.remove(item)
    identified, unrecognised = [], []
    for number in details.card_numbers:
        card = _identify_card(session, number, details, text, cfg)
        if card:
            lot.items.append(LotItem(card_id=card.id, quantity=1, origin="auto", label=f"{card.name} {number}"))
            identified.append(f"{card.name} {card.card_number}")
        else:
            unrecognised.append(number)
    for product in _identify_products(session, details):
        lot.items.append(LotItem(product_id=product.id, quantity=1, origin="auto", label=product.name))
        identified.append(product.name)
    lot.stated_quantity = details.stated_quantity
    lot.extraction = {**details.as_dict(), "identified": identified, "unrecognised_numbers": unrecognised,
                      "rule": "identified = unique set+number match AND Pokémon named; others unvalued"}
    return lot


def safety_flags(session: Session, listing: Listing) -> list[str]:
    """Neutral labels for the buyer to check. Never accusations."""
    flags: list[str] = []
    desc = (listing.description or "").strip()
    if len(desc) < LOW_INFO_CHARS:
        flags.append("low information: very short description")
    if listing.capture_method == "capture" and not listing.image_urls:
        flags.append("verify listing: no photos captured")
    if listing.published_at and utcnow() - listing.published_at < timedelta(hours=2):
        flags.append("very new listing")
    dupes = session.scalar(select(func.count(Listing.id)).where(
        Listing.source == listing.source, Listing.id != listing.id, Listing.status == ListingStatus.ACTIVE,
        func.lower(Listing.title) == listing.title.lower(), Listing.asking_price == listing.asking_price))
    if dupes:
        flags.append("duplicate-looking listing: same title and price seen elsewhere")
    if listing.seller:
        same_seller = session.scalar(select(func.count(Listing.id)).where(
            Listing.source == listing.source, Listing.seller == listing.seller,
            Listing.status == ListingStatus.ACTIVE)) or 0
        if same_seller >= 5:
            flags.append(f"repeated seller: {same_seller} active listings")
    if listing.seller_type == "business":
        flags.append("business seller")
    return flags


def analyse_finn_listing(session: Session, listing: Listing) -> LotDetails:
    """Run after ingest: lot detection (overrides a single-card match), then safety labels."""
    cfg = get_user_config()
    details = extract_lot_details(listing.title, listing.description, cfg.sets, pokemon_names(session, cfg))
    extracted = dict(listing.extracted or {})
    extracted["lot"] = details.as_dict()
    if details.is_lot:
        listing.listing_kind = "lot"
        # A lot is never forced into a single-card identity.
        listing.matched_card_id = listing.matched_product_id = None
        listing.match_status, listing.confidence = MatchStatus.UNRESOLVED, 0.0
        analyse_lot(session, listing, details)
    listing.extracted = extracted
    listing.safety_flags = safety_flags(session, listing)
    session.flush()
    return details

"""Housekeeping for data that must not influence live pricing: mock rows and stale price models."""

from __future__ import annotations

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.collectors.cardtrader_mock import MOCK_BLUEPRINT_IDS
from app.db.models import (
    Alert,
    Card,
    DealEvaluation,
    EntityType,
    GradedPriceReference,
    Listing,
    LotItem,
    PortfolioItem,
    PriceDaily,
    PriceSnapshot,
    Product,
    WatchlistItem,
)
from app.matching.normalize import fold, split_card_number


def _is_mock(row: Card | Product) -> bool:
    return (row.source_ids or {}).get("cardtrader") in MOCK_BLUEPRINT_IDS


def _live_twin(session: Session, card: Card) -> Card | None:
    number = split_card_number(card.card_number)[0]
    for other in session.scalars(select(Card).where(Card.set_code == card.set_code, Card.id != card.id)).all():
        ct = (other.source_ids or {}).get("cardtrader")
        if ct and ct not in MOCK_BLUEPRINT_IDS and split_card_number(other.card_number)[0] == number \
                and fold(other.name) == fold(card.name):
            return other
    return None


def _delete_listings(session: Session, listing_ids: list[int]) -> int:
    if not listing_ids:
        return 0
    ev_ids = select(DealEvaluation.id).where(DealEvaluation.listing_id.in_(listing_ids))
    session.execute(delete(Alert).where(or_(Alert.listing_id.in_(listing_ids), Alert.deal_evaluation_id.in_(ev_ids))))
    session.execute(delete(DealEvaluation).where(DealEvaluation.listing_id.in_(listing_ids)))
    return session.execute(delete(Listing).where(Listing.id.in_(listing_ids))).rowcount or 0


def purge_mock_data(session: Session) -> dict[str, int]:
    """Remove everything that came from the mock CardTrader client.

    User data (watchlist, portfolio, lots, graded refs) pointing at a mock card is moved to
    the live card with the same set + number + name. Without a live twin, the card is kept
    as a manual catalogue entry (mock id stripped) so the next live sync adopts it.
    """
    out = {"cards_merged": 0, "cards_detached": 0, "cards_deleted": 0, "products_deleted": 0, "listings_deleted": 0,
           "snapshots_deleted": 0}
    for card in [c for c in session.scalars(select(Card)).all() if _is_mock(c)]:
        _purge_prices(session, EntityType.CARD, card.id, out)
        out["listings_deleted"] += _delete_listings(session, list(session.scalars(
            select(Listing.id).where(Listing.matched_card_id == card.id, Listing.source == "cardtrader"))))
        twin = _live_twin(session, card)
        if twin is None:
            if _card_in_use(session, card.id):
                card.source_ids = {k: v for k, v in (card.source_ids or {}).items() if k != "cardtrader"}
                out["cards_detached"] += 1
            else:
                session.delete(card)
                out["cards_deleted"] += 1
            continue
        session.query(WatchlistItem).filter(WatchlistItem.target_type == "card",
                                            WatchlistItem.entity_id == card.id).update({"entity_id": twin.id})
        for model in (PortfolioItem, LotItem, GradedPriceReference):
            session.query(model).filter(model.card_id == card.id).update({"card_id": twin.id})
        session.query(Listing).filter(Listing.matched_card_id == card.id).update({"matched_card_id": twin.id})
        session.delete(card)
        out["cards_merged"] += 1
    for product in [p for p in session.scalars(select(Product)).all() if _is_mock(p)]:
        _purge_prices(session, EntityType.PRODUCT, product.id, out)
        out["listings_deleted"] += _delete_listings(session, list(session.scalars(
            select(Listing.id).where(Listing.matched_product_id == product.id))))
        in_use = session.scalar(select(PortfolioItem.id).where(PortfolioItem.product_id == product.id)) or \
            session.scalar(select(WatchlistItem.id).where(WatchlistItem.target_type == "product",
                                                          WatchlistItem.entity_id == product.id))
        if in_use:
            product.source_ids = {k: v for k, v in (product.source_ids or {}).items() if k != "cardtrader"}
        else:
            session.delete(product)
            out["products_deleted"] += 1
    session.flush()
    return out


def _card_in_use(session: Session, card_id: int) -> bool:
    return any(session.scalar(q) for q in (
        select(WatchlistItem.id).where(WatchlistItem.target_type == "card", WatchlistItem.entity_id == card_id),
        select(PortfolioItem.id).where(PortfolioItem.card_id == card_id),
        select(LotItem.id).where(LotItem.card_id == card_id),
        select(GradedPriceReference.id).where(GradedPriceReference.card_id == card_id),
        select(Listing.id).where(Listing.matched_card_id == card_id),
    ))


def _purge_prices(session: Session, etype: str, eid: int, out: dict[str, int]) -> None:
    out["snapshots_deleted"] += session.execute(delete(PriceSnapshot).where(
        PriceSnapshot.entity_type == etype, PriceSnapshot.entity_id == eid)).rowcount or 0
    session.execute(delete(PriceDaily).where(PriceDaily.entity_type == etype, PriceDaily.entity_id == eid))


def reset_price_history(session: Session) -> dict[str, int]:
    """Drop all derived price data and un-alerted evaluations (e.g. after a pricing-model change).

    Listings, catalogue, portfolio, watchlist and sent alerts are kept.
    """
    alerted = select(Alert.deal_evaluation_id).where(Alert.deal_evaluation_id.is_not(None))
    return {
        "snapshots_deleted": session.execute(delete(PriceSnapshot)).rowcount or 0,
        "daily_deleted": session.execute(delete(PriceDaily)).rowcount or 0,
        "evaluations_deleted": session.execute(
            delete(DealEvaluation).where(DealEvaluation.id.not_in(alerted))).rowcount or 0,
    }


def mock_rows_present(session: Session) -> bool:
    return any(_is_mock(c) for c in session.scalars(select(Card)).all())

"""Optional starter watchlist. These are examples, NOT investment recommendations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_user_config
from app.db.models import Card, WatchlistItem

STARTER_WATCHLIST = [
    # name, set code, number, rarity, target NOK (None = alert on score only)
    ("Gastly", "TEF", "177/162", "Special Illustration Rare", None),
    ("Raichu", "PAL", "211/193", "Illustration Rare", None),
    ("Tyranitar", "PAL", "222/193", "Illustration Rare", None),
    ("Eevee", "TWM", "188/167", "Illustration Rare", None),
    ("Pikachu", "MEW", "173/165", "Illustration Rare", None),
]


def seed_watchlist(session: Session) -> list[str]:
    cfg = get_user_config()
    added = []
    for name, code, number, rarity, target in STARTER_WATCHLIST:
        card = session.scalar(select(Card).where(Card.set_code == code, Card.card_number == number,
                                                 Card.name == name))
        if card is None:
            meta = cfg.sets.find(code)
            card = Card(name=name, pokemon_name=name, set_code=code, set_name=meta.name if meta else code,
                        card_number=number, rarity=rarity, language="en",
                        release_date=meta.release_date if meta else None, source_ids={})
            session.add(card)
            session.flush()
        exists = session.scalar(select(WatchlistItem).where(WatchlistItem.target_type == "card",
                                                            WatchlistItem.entity_id == card.id))
        if not exists:
            session.add(WatchlistItem(entity_id=card.id, target_type="card", target_buy_price=target,
                                      priority="high", enabled=True,
                                      notes="starter example — not a guaranteed investment"))
            added.append(f"{name} {number} ({code})")
    return added

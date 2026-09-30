"""Everything the scoring engine needs, gathered up-front so scoring stays pure."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.portfolio.modifiers import PortfolioState
from app.pricing.fair_value import FairValue
from app.pricing.history import HistoryStats


@dataclass
class EvaluationContext:
    # listing
    source: str
    title: str
    # All-in price used for discount/score/alerts = estimated landed cost
    # (item + shipping + import buffer). Component parts are kept for display.
    total_price_nok: float
    listing_price_nok: float | None = None
    shipping_nok: float = 0.0
    import_buffer_nok: float = 0.0
    seller_country: str | None = None
    seller_region: str | None = None
    listing_kind: str = "single"          # single|sealed|lot|graded
    condition: str | None = None
    description: str | None = None
    seller_rating: float | None = None    # 0..1 normalised if known
    seller_verified: bool = False         # e.g. CardTrader Zero / hub seller
    match_confidence: float = 1.0
    quantity: int = 1
    # entity
    entity_type: str | None = None        # card|product
    entity_name: str | None = None
    pokemon_name: str | None = None
    rarity: str | None = None
    set_code: str | None = None
    set_name: str | None = None
    card_number: str | None = None
    product_type: str | None = None
    pack_count: int | None = None
    release_date: date | None = None
    # market
    fair_value: FairValue | None = None
    history: HistoryStats = field(default_factory=HistoryStats)
    listing_count: int = 0
    # grading refs
    psa9_nok: float | None = None
    psa10_nok: float | None = None
    # sealed extras
    loose_pack_value_nok: float | None = None
    top_chase_value_nok: float | None = None
    # user state
    portfolio: PortfolioState = field(default_factory=PortfolioState)
    watchlist_target_nok: float | None = None
    watchlist_priority: str | None = None
    is_premium_target: bool = False

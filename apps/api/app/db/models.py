"""SQLAlchemy models. All money columns ending in ``_nok`` are Norwegian kroner."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class EntityType(StrEnum):
    CARD = "card"
    PRODUCT = "product"


class ProductType(StrEnum):
    BOOSTER_PACK = "booster_pack"
    BOOSTER_BUNDLE = "booster_bundle"
    BOOSTER_BOX = "booster_box"
    ETB = "etb"
    UPC = "upc"
    COLLECTION_BOX = "collection_box"
    TIN = "tin"
    LOT = "lot"
    OTHER = "other"


class ListingStatus(StrEnum):
    ACTIVE = "active"
    GONE = "gone"
    SOLD = "sold"
    IGNORED = "ignored"


class MatchStatus(StrEnum):
    AUTO = "auto"            # confidence >= 0.90
    REVIEW = "review"        # 0.70 – 0.89, waiting for a human
    UNRESOLVED = "unresolved"
    MANUAL = "manual"        # confirmed by a human
    REJECTED = "rejected"    # human said: no match


class BinderType(StrEnum):
    REGULAR = "regular"
    PREMIUM = "premium"
    GRADED = "graded"
    SEALED = "sealed"


class Recommendation(StrEnum):
    IGNORE = "IGNORE"
    WATCH = "WATCH"
    GOOD = "GOOD"
    STRONG_BUY = "STRONG_BUY"
    STEAL = "STEAL"


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = (Index("ix_cards_set_number", "set_code", "card_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    set_name: Mapped[str | None] = mapped_column(String(200))
    set_code: Mapped[str | None] = mapped_column(String(32))
    card_number: Mapped[str | None] = mapped_column(String(32))
    rarity: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(8), default="en")
    pokemon_name: Mapped[str | None] = mapped_column(String(100), index=True)
    release_date: Mapped[date | None] = mapped_column(Date)
    image_url: Mapped[str | None] = mapped_column(String(500))
    is_promo: Mapped[bool] = mapped_column(Boolean, default=False)
    source_ids: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_type: Mapped[str] = mapped_column(String(32), index=True)
    set_name: Mapped[str | None] = mapped_column(String(200))
    set_code: Mapped[str | None] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(300))
    pack_count: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(8), default="en")
    release_date: Mapped[date | None] = mapped_column(Date)
    image_url: Mapped[str | None] = mapped_column(String(500))
    source_ids: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_listings_source_external"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(String(2048))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    seller: Mapped[str | None] = mapped_column(String(200))
    seller_rating: Mapped[float | None] = mapped_column(Float)
    condition: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(8))
    is_graded: Mapped[bool] = mapped_column(Boolean, default=False)
    grade_company: Mapped[str | None] = mapped_column(String(16))
    grade: Mapped[float | None] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    listing_kind: Mapped[str] = mapped_column(String(16), default="single")  # single|sealed|lot|graded
    asking_price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="NOK")
    normalized_price_nok: Mapped[float] = mapped_column(Float)
    shipping_price_nok: Mapped[float] = mapped_column(Float, default=0)
    total_price_nok: Mapped[float] = mapped_column(Float, index=True)
    previous_total_price_nok: Mapped[float | None] = mapped_column(Float)
    image_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    status: Mapped[str] = mapped_column(String(16), default=ListingStatus.ACTIVE, index=True)
    matched_card_id: Mapped[int | None] = mapped_column(ForeignKey("cards.id"), index=True)
    matched_product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    match_status: Mapped[str] = mapped_column(String(16), default=MatchStatus.UNRESOLVED, index=True)
    match_candidates: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    card: Mapped[Card | None] = relationship()
    product: Mapped[Product | None] = relationship()


class PriceSnapshot(Base):
    """Raw market observation (one per collector run per entity). Prices in NOK."""

    __tablename__ = "price_snapshots"
    __table_args__ = (Index("ix_snap_entity_ts", "entity_type", "entity_id", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(16))
    entity_id: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(32))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    low_price: Mapped[float | None] = mapped_column(Float)
    median_price: Mapped[float | None] = mapped_column(Float)
    trimmed_median: Mapped[float | None] = mapped_column(Float)
    cheapest5_median: Mapped[float | None] = mapped_column(Float)
    listing_count: Mapped[int] = mapped_column(Integer, default=0)
    seller_count: Mapped[int | None] = mapped_column(Integer)
    dispersion: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="NOK")


class PriceDaily(Base):
    """Daily aggregate of snapshots; kept forever (raw snapshots are pruned)."""

    __tablename__ = "price_daily"
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", "source", "day", name="uq_price_daily"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(16))
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    source: Mapped[str] = mapped_column(String(32))
    day: Mapped[date] = mapped_column(Date, index=True)
    low_price: Mapped[float | None] = mapped_column(Float)
    median_price: Mapped[float | None] = mapped_column(Float)
    trimmed_median: Mapped[float | None] = mapped_column(Float)
    listing_count: Mapped[float | None] = mapped_column(Float)
    samples: Mapped[int] = mapped_column(Integer, default=0)


class PortfolioItem(Base):
    __tablename__ = "portfolio_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int | None] = mapped_column(ForeignKey("cards.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    acquisition_price_nok: Mapped[float] = mapped_column(Float, default=0)  # per unit
    acquisition_date: Mapped[date | None] = mapped_column(Date)
    binder_type: Mapped[str] = mapped_column(String(16), default=BinderType.REGULAR)
    condition: Mapped[str | None] = mapped_column(String(32))
    grading_status: Mapped[str] = mapped_column(String(16), default="raw")  # raw|submitted|graded
    grade_company: Mapped[str | None] = mapped_column(String(16))
    psa_grade: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    card: Mapped[Card | None] = relationship()
    product: Mapped[Product | None] = relationship()


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(Date, unique=True)
    total_cost_nok: Mapped[float] = mapped_column(Float)
    raw_value_nok: Mapped[float] = mapped_column(Float)
    graded_value_nok: Mapped[float] = mapped_column(Float)
    by_binder: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(Integer)
    target_type: Mapped[str] = mapped_column(String(16), default=EntityType.CARD)  # card|product
    target_buy_price: Mapped[float | None] = mapped_column(Float)  # NOK
    priority: Mapped[str] = mapped_column(String(8), default="normal")  # high|normal|low
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DealEvaluation(Base):
    __tablename__ = "deal_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    price_nok: Mapped[float] = mapped_column(Float)
    fair_value_nok: Mapped[float | None] = mapped_column(Float)
    fair_value_low: Mapped[float | None] = mapped_column(Float)
    fair_value_high: Mapped[float | None] = mapped_column(Float)
    fair_value_confidence: Mapped[float | None] = mapped_column(Float)
    discount_pct: Mapped[float | None] = mapped_column(Float)
    liquidity_score: Mapped[float] = mapped_column(Float, default=0)
    popularity_score: Mapped[float] = mapped_column(Float, default=0)
    set_score: Mapped[float] = mapped_column(Float, default=0)
    trend_score: Mapped[float] = mapped_column(Float, default=0)
    grading_score: Mapped[float] = mapped_column(Float, default=0)
    scarcity_score: Mapped[float] = mapped_column(Float, default=0)
    portfolio_score: Mapped[float] = mapped_column(Float, default=0)
    seller_confidence_score: Mapped[float] = mapped_column(Float, default=0)
    total_score: Mapped[float] = mapped_column(Float, index=True)
    recommendation: Mapped[str] = mapped_column(String(16), index=True)
    binder_fit: Mapped[str | None] = mapped_column(String(16))
    reason_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    listing: Mapped[Listing] = relationship()


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_evaluation_id: Mapped[int | None] = mapped_column(ForeignKey("deal_evaluations.id"))
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("listings.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="deal")  # deal|health|digest|test
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    severity: Mapped[str] = mapped_column(String(16))
    price_nok: Mapped[float | None] = mapped_column(Float)
    telegram_message_id: Mapped[int | None] = mapped_column(Integer)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    message: Mapped[str | None] = mapped_column(Text)


class GradedPriceReference(Base):
    __tablename__ = "graded_price_references"
    __table_args__ = (UniqueConstraint("card_id", "grade_company", "grade", "source", name="uq_graded_ref"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True)
    grade_company: Mapped[str] = mapped_column(String(16), default="PSA")
    grade: Mapped[float] = mapped_column(Float)
    price_nok: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), default="manual")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    confidence: Mapped[float] = mapped_column(Float, default=0.7)


class Lot(Base):
    """Manual lot / collection breakdown attached to a listing."""

    __tablename__ = "lots"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), unique=True)
    images: Mapped[list[str]] = mapped_column(JSON, default=list)  # stored file names
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    items: Mapped[list[LotItem]] = relationship(cascade="all, delete-orphan", back_populates="lot")


class LotItem(Base):
    __tablename__ = "lot_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="CASCADE"), index=True)
    card_id: Mapped[int | None] = mapped_column(ForeignKey("cards.id"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    label: Mapped[str | None] = mapped_column(String(200))  # free text when not in catalogue
    manual_value_nok: Mapped[float | None] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    condition: Mapped[str | None] = mapped_column(String(32))

    lot: Mapped[Lot] = relationship(back_populates="items")


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    __table_args__ = (UniqueConstraint("day", "currency", name="uq_fx_day_currency"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    currency: Mapped[str] = mapped_column(String(3))
    nok_per_unit: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), default="frankfurter")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SourceStatus(Base):
    __tablename__ = "source_status"

    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    last_success: Mapped[datetime | None] = mapped_column(DateTime)
    last_failure: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    health_alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    running_since: Mapped[datetime | None] = mapped_column(DateTime)


class CollectorRun(Base):
    __tablename__ = "collector_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    items_fetched: Mapped[int] = mapped_column(Integer, default=0)
    items_matched: Mapped[int] = mapped_column(Integer, default=0)
    listings_evaluated: Mapped[int] = mapped_column(Integer, default=0)
    deals_found: Mapped[int] = mapped_column(Integer, default=0)
    alerts_sent: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)

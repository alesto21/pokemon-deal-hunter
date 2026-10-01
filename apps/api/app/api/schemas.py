"""Request bodies (validated with Pydantic v2)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

BinderLiteral = Literal["regular", "premium", "graded", "sealed"]


class ManualListingIn(BaseModel):
    url: HttpUrl
    title: str | None = Field(default=None, max_length=500)
    price: float | None = Field(default=None, ge=0, le=10_000_000)
    currency: str = Field(default="NOK", min_length=3, max_length=3)
    shipping_nok: float | None = Field(default=None, ge=0, le=100_000)
    condition: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=4000)
    fetch_metadata: bool | None = None


class ListingPatch(BaseModel):
    status: Literal["active", "gone", "sold", "ignored"] | None = None
    listing_kind: Literal["single", "sealed", "lot", "graded"] | None = None


class ReviewDecision(BaseModel):
    action: Literal["accept", "reject", "set"]
    entity_type: Literal["card", "product"] | None = None
    entity_id: int | None = None


class CardIn(BaseModel):
    name: str = Field(max_length=200)
    set_name: str | None = Field(default=None, max_length=200)
    set_code: str | None = Field(default=None, max_length=32)
    card_number: str | None = Field(default=None, max_length=32)
    rarity: str | None = Field(default=None, max_length=64)
    language: str = Field(default="en", max_length=8)
    pokemon_name: str | None = Field(default=None, max_length=100)
    release_date: date | None = None
    image_url: HttpUrl | None = None
    is_promo: bool = False


class ProductIn(BaseModel):
    name: str = Field(max_length=300)
    product_type: Literal["booster_pack", "booster_bundle", "booster_box", "etb", "upc", "collection_box",
                          "tin", "other"]
    set_name: str | None = None
    set_code: str | None = None
    pack_count: int | None = Field(default=None, ge=0, le=1000)
    language: str = "en"
    release_date: date | None = None


class PortfolioIn(BaseModel):
    card_id: int | None = None
    product_id: int | None = None
    quantity: int = Field(default=1, ge=1, le=10_000)
    acquisition_price_nok: float = Field(default=0, ge=0)
    acquisition_date: date | None = None
    binder_type: BinderLiteral = "regular"
    condition: str | None = Field(default="Near Mint", max_length=32)
    grading_status: Literal["raw", "submitted", "at_grader", "graded"] = "raw"
    grade_company: str | None = Field(default=None, max_length=16)
    psa_grade: float | None = Field(default=None, ge=1, le=10)
    notes: str | None = Field(default=None, max_length=2000)


class PortfolioPatch(BaseModel):
    quantity: int | None = Field(default=None, ge=1)
    acquisition_price_nok: float | None = Field(default=None, ge=0)
    acquisition_date: date | None = None
    binder_type: BinderLiteral | None = None
    condition: str | None = None
    grading_status: Literal["raw", "submitted", "at_grader", "graded"] | None = None
    grade_company: str | None = None
    psa_grade: float | None = Field(default=None, ge=1, le=10)
    notes: str | None = None


class WatchlistIn(BaseModel):
    entity_id: int
    target_type: Literal["card", "product"] = "card"
    target_buy_price: float | None = Field(default=None, ge=0)
    priority: Literal["high", "normal", "low"] = "normal"
    enabled: bool = True
    notes: str | None = Field(default=None, max_length=1000)


class WatchlistPatch(BaseModel):
    target_buy_price: float | None = Field(default=None, ge=0)
    priority: Literal["high", "normal", "low"] | None = None
    enabled: bool | None = None
    notes: str | None = None


class GradedRefIn(BaseModel):
    card_id: int
    grade_company: str = Field(default="PSA", max_length=16)
    grade: float = Field(ge=1, le=10)
    price_nok: float = Field(gt=0)
    source: str = Field(default="manual", max_length=64)
    confidence: float = Field(default=0.7, ge=0, le=1)


class LotIn(BaseModel):
    listing_id: int
    notes: str | None = Field(default=None, max_length=2000)


class LotItemIn(BaseModel):
    card_id: int | None = None
    product_id: int | None = None
    label: str | None = Field(default=None, max_length=200)
    manual_value_nok: float | None = Field(default=None, ge=0)
    quantity: int = Field(default=1, ge=1, le=10_000)
    condition: str | None = Field(default=None, max_length=32)

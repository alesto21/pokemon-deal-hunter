"""Which CardTrader listings are allowed to define market prices.

Every exclusion has an explicit reason so ``cardtrader-debug-card`` can show exactly
why a listing did or did not count. The same function is used by the collector.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.core.config import CardTraderSourceConfig

# Graded / foreign / fake indications that CardTrader's structured fields may miss.
_GRADED_TEXT = re.compile(r"\b(psa|bgs|cgc|sgc|beckett|graded|gradert|slab(bed)?)\b", re.I)
_FOREIGN_TEXT = re.compile(r"\b(japanese|japan|jpn|jp|korean|chinese|german|italian|french|spanish|"
                           r"japansk|not english)\b", re.I)
_FAKE_TEXT = re.compile(r"\b(proxy|replica|fake|custom|orica|reprint|fan ?made)\b", re.I)


@dataclass
class ListingVerdict:
    product: dict[str, Any]
    included: bool
    reason: str | None = None

    @property
    def price_cents(self) -> int:
        return int(self.product["price"]["cents"])

    @property
    def seller_id(self) -> str:
        user = self.product.get("user") or {}
        return str(user.get("id") or user.get("username") or self.product.get("id"))


def exclusion_reason(p: dict[str, Any], cfg: CardTraderSourceConfig) -> str | None:
    """Return why a listing must NOT be used for pricing, or None if it is valid."""
    props = p.get("properties_hash") or {}
    price = (p.get("price") or {}).get("cents") or 0
    description = p.get("description") or ""
    if price <= 0:
        return "no price"
    lang = props.get("pokemon_language")
    if cfg.languages and lang not in cfg.languages:
        return f"language {lang or 'unknown'}"
    if cfg.exclude_graded and p.get("graded"):
        return "graded (flag)"
    if cfg.exclude_graded and _GRADED_TEXT.search(description):
        return "graded (description)"
    cond = props.get("condition")
    # Sealed products carry no condition; singles must have an accepted one.
    if "condition" in props and cfg.accepted_conditions and cond not in cfg.accepted_conditions:
        return f"condition {cond or 'unknown'}"
    if cfg.exclude_reverse_holo and props.get("pokemon_reverse"):
        return "reverse holo variant"
    if props.get("first_edition"):
        return "1st edition variant"
    if props.get("signed"):
        return "signed"
    if props.get("altered"):
        return "altered"
    if _FAKE_TEXT.search(description):
        return "description red flag"
    if _FOREIGN_TEXT.search(description):
        return "description suggests non-English"
    if p.get("on_vacation"):
        return "seller on vacation"
    if (p.get("bundle_size") or 1) > 1:
        return "bundle listing"
    return None


def classify_listings(products: list[dict[str, Any]], cfg: CardTraderSourceConfig) -> list[ListingVerdict]:
    """Classify all listings (sorted by price). Only the cheapest listing per seller counts,
    so one seller with many copies cannot fill the cheapest-N window alone."""
    verdicts = []
    for p in sorted(products, key=lambda p: (p.get("price") or {}).get("cents") or 0):
        reason = exclusion_reason(p, cfg)
        verdicts.append(ListingVerdict(p, reason is None, reason))
    seen_sellers: set[str] = set()
    for v in verdicts:
        if not v.included:
            continue
        if cfg.one_listing_per_seller and v.seller_id in seen_sellers:
            v.included, v.reason = False, "same seller already counted"
        seen_sellers.add(v.seller_id)
    return verdicts

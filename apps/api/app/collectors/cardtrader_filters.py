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
    _exclude_absurd_asks(verdicts, cfg.absurd_ask_multiple)
    return verdicts


def lower_market_base(cents: list[int]) -> float | None:
    """Price level of the liquid lower-market cluster: median of the cheapest half (max 5).

    One cheap listing among several cannot drag it down much; a single placeholder ask
    can never raise it, because only the cheaper half is used.
    """
    if not cents:
        return None
    vals = sorted(cents)
    k = min(5, max(1, (len(vals) + 1) // 2))
    window = vals[:k]
    mid = len(window) // 2
    return float(window[mid]) if len(window) % 2 else (window[mid - 1] + window[mid]) / 2


def _exclude_absurd_asks(verdicts: list[ListingVerdict], multiple: float) -> None:
    """Placeholder / absurd asks (e.g. 10 000 EUR on a ~35 EUR card) are excluded relative to
    the lower-market cluster — never by a fixed price. They stay visible in diagnostics and in
    the excluded count, but never feed stats, history, liquidity or fair value."""
    if multiple <= 0:
        return
    base = lower_market_base([v.price_cents for v in verdicts if v.included])
    if not base:
        return
    for v in verdicts:
        if v.included and v.price_cents > base * multiple:
            v.included = False
            v.reason = f"absurd ask (>{multiple:g}x lower-market {base / 100:.2f})"

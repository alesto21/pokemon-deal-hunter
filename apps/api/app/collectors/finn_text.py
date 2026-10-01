"""Deterministic analysis of FINN listing text (title + description). No network access.

* shipping: exact amount / included / pickup-only / unknown (Norwegian + English phrasing)
* lot detection: collections, binders, bulk, mixed sealed lots — with extraction of mentioned
  Pokémon, set names, card numbers, PSA grades, sealed products and stated quantity
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from app.core.config import SetsConfig
from app.matching.normalize import PRODUCT_KEYWORDS, fold, normalize_number

_NUM = r"(\d{1,3}(?:[ .]\d{3})*|\d+)"

# ------------------------------------------------------------------ shipping
_SHIP_AMOUNT = [
    re.compile(rf"(?:frakt|porto|sending|shipping)\s*(?:koster|er|:|=|-|kr\.?|nok)?\s*(?:kr\.?|nok)?\s*"
               rf"{_NUM}\s*(?:kr|,-|nok)?", re.I),
    re.compile(rf"{_NUM}\s*(?:kr|,-|nok)\.?\s*(?:i\s*)?(?:frakt|porto)", re.I),
]
_INCLUDED = re.compile(r"\b(fri frakt|gratis frakt|fraktfri|frakt inkl\w*|inkl\.?\s*frakt|frakt er inkludert|"
                       r"frakt inkludert|free shipping|shipping included|sendes gratis)\b", re.I)
_PICKUP_ONLY = re.compile(r"\b(kun henting|kun hentes|m[åa] hentes|hentes kun|sendes ikke|ingen sending|"
                          r"pickup only|kan ikke sendes)\b", re.I)
_PICKUP_POSSIBLE = re.compile(r"\b(kan hentes|hentes i|henting i|kan m[øo]tes|pickup)\b", re.I)
_SHIPPABLE = re.compile(r"\b(fiks ferdig|kan sendes|sender gjerne|sendes med|sendes|posten|bring)\b", re.I)


@dataclass
class ShippingInfo:
    kind: str                 # exact | included | pickup | unknown
    amount_nok: float | None = None
    pickup_possible: bool = False
    shippable: bool | None = None   # None = not stated
    evidence: str | None = None


def _to_int(s: str) -> float:
    return float(re.sub(r"[ .]", "", s))


def parse_shipping(text: str | None) -> ShippingInfo:
    t = text or ""
    if _PICKUP_ONLY.search(t):
        return ShippingInfo("pickup", 0.0, True, False, _PICKUP_ONLY.search(t).group(0))
    if m := _INCLUDED.search(t):
        return ShippingInfo("included", 0.0, bool(_PICKUP_POSSIBLE.search(t)), True, m.group(0))
    for pat in _SHIP_AMOUNT:
        if m := pat.search(t):
            amount = _to_int(m.group(1))
            if 0 < amount <= 1000:  # a plausible parcel price, not a card price
                return ShippingInfo("exact", amount, bool(_PICKUP_POSSIBLE.search(t)), True, m.group(0).strip())
    return ShippingInfo("unknown", None, bool(_PICKUP_POSSIBLE.search(t)),
                        True if _SHIPPABLE.search(t) else None)


# ------------------------------------------------------------------ lots
LOT_WORDS = ("samling", "kortsamling", "lot", "bulk", "bundle av", "perm", "binder", "mappe", "album",
             "mange kort", "masse kort", "diverse kort", "blandet", "blanding", "collection", "bunke",
             "eske med kort", "boks med kort", "kort selges samlet", "selges samlet", "pakke med kort")
_QTY = re.compile(r"(?<![\d/])(\d{1,5})\s*(?:\+\s*)?(?:stk|stykker|kort|cards|pcs|pokemonkort|pokémonkort)\b", re.I)
_CARD_NUMBER = re.compile(r"(?<![\w/])([A-Z]{0,4}\d{1,3}[a-z]?)\s*/\s*([A-Z]{0,4}\d{1,3})(?![\w/])", re.I)
_GRADE = re.compile(r"\b(PSA|BGS|CGC|SGC)\s*(10|\d(?:\.5)?)\b", re.I)


@dataclass
class LotDetails:
    is_lot: bool
    lot_score: float                     # 0..1 how strongly the text describes a lot
    reasons: list[str] = field(default_factory=list)
    stated_quantity: int | None = None
    card_numbers: list[str] = field(default_factory=list)       # "177/162"
    pokemon: list[str] = field(default_factory=list)
    sets: list[str] = field(default_factory=list)              # set codes
    grades: list[str] = field(default_factory=list)            # "PSA 10"
    sealed_products: list[str] = field(default_factory=list)   # product types

    def as_dict(self) -> dict:
        return asdict(self)


def _word_hit(word: str, text: str) -> bool:
    return re.search(rf"(?<![\w]){re.escape(word)}(?![\w])", text) is not None


def extract_lot_details(title: str, description: str | None, sets: SetsConfig,
                        pokemon_names: list[str] | None = None) -> LotDetails:
    """Is this a lot/collection, and what does the text say is in it? Never guesses values."""
    text = f"{title}\n{description or ''}"
    folded = fold(text)
    reasons: list[str] = []
    score = 0.0

    words = [w for w in LOT_WORDS if _word_hit(fold(w), folded)]
    if words:
        score += 0.6
        reasons.append(f"lot words: {', '.join(words[:4])}")

    quantities = [int(m.group(1)) for m in _QTY.finditer(text)]
    qty = max(quantities) if quantities else None
    if qty and qty >= 5:
        score += 0.3 if qty < 20 else 0.5
        reasons.append(f"states {qty} cards/items")

    numbers = []
    for m in _CARD_NUMBER.finditer(text):
        n = f"{normalize_number(m.group(1))}/{normalize_number(m.group(2))}"
        if n not in numbers:
            numbers.append(n)
    if len(numbers) >= 3:
        score += 0.4
        reasons.append(f"{len(numbers)} different card numbers")

    sealed = []
    padded = f" {folded} "
    for ptype, kws in PRODUCT_KEYWORDS:
        if any(k in padded for k in kws) and ptype not in sealed:
            sealed.append(ptype)
    if len(sealed) >= 2:
        score += 0.3
        reasons.append(f"mixed sealed products: {', '.join(sealed)}")

    found_sets = []
    for s in sets.sets:
        for alias in [s.name, *s.aliases]:
            a = fold(alias)
            hit = _word_hit(a, folded) if len(a) <= 3 else a in folded
            if hit and s.code not in found_sets:
                found_sets.append(s.code)
                break

    mons = sorted({p for p in (pokemon_names or []) if len(p) >= 3 and _word_hit(fold(p), folded)})
    if len(mons) >= 4:
        score += 0.2
        reasons.append(f"mentions {len(mons)} Pokémon")

    grades = sorted({f"{m.group(1).upper()} {m.group(2)}" for m in _GRADE.finditer(text)})
    if len(_GRADE.findall(text)) >= 2:
        score += 0.2
        reasons.append("several graded cards")

    score = round(min(score, 1.0), 2)
    return LotDetails(score >= 0.5, score, reasons, qty, numbers, mons, found_sets, grades, sealed)

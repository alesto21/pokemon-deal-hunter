"""Deterministic title parsing for free-text listings (FINN, stores, CSV imports)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.core.config import SetsConfig

_NUMBER = re.compile(r"(?<![\w/])([A-Z]{0,4}\d{1,3}[a-z]?)\s*/\s*([A-Z]{0,4}\d{1,3})(?![\w/])", re.I)
_PROMO = re.compile(r"\b(SVP|SWSH|SM|XY|BW|MEP)\s*[- ]?\s*(\d{1,3})\b", re.I)
_HASH_NUMBER = re.compile(r"#\s*(\d{1,3})\b")
_GRADE = re.compile(r"\b(PSA|BGS|CGC|SGC|TAG)\s*(10|\d(?:\.5)?)\b", re.I)

# Order matters: more specific patterns first.
PRODUCT_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("upc", ("ultra premium collection", " upc")),
    ("etb", ("elite trainer box", "etb", "trener boks", "trainer box")),
    ("booster_bundle", ("booster bundle", "bundle")),
    ("booster_box", ("booster box", "booster display", "display", "36 packs", "36 pakker", "booster boks")),
    ("tin", (" tin", "tinboks", "blikkboks")),
    ("collection_box", ("collection box", "premium collection", "collection", "kolleksjon")),
    ("booster_pack", ("booster pack", "booster pakke", "boosterpakke", "sleeved booster", "blister")),
]
LOT_KEYWORDS = ("samling", "lot ", " lot", "bulk", "kortsamling", "mange kort", "collection of", "binder full",
                "perm med", "diverse kort")
JAPANESE = ("japansk", "japanese", " jp ", "(jp)", "jpn", "japan")
CONDITION_WORDS = {
    "mint": "Mint", "near mint": "Near Mint", "nm": "Near Mint", "ny": "Near Mint", "som ny": "Near Mint",
    "lp": "Slightly Played", "light played": "Slightly Played", "lightly played": "Slightly Played",
    "played": "Played", "mp": "Moderately Played", "damaged": "Damaged", "skadet": "Damaged",
}


def fold(text: str) -> str:
    """Lower-case, strip accents (é→e), collapse whitespace."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower()).strip()


def normalize_number(num: str | None) -> str | None:
    """'007' → '7', 'TG05' → 'TG5', 'SVP 085' → 'SVP85'."""
    if not num:
        return None
    m = re.match(r"^([A-Za-z]*)\s*-?\s*0*(\d+)([a-z]?)$", num.strip())
    if not m:
        return num.strip().upper()
    return f"{m.group(1).upper()}{int(m.group(2))}{m.group(3)}"


def split_card_number(card_number: str | None) -> tuple[str | None, str | None]:
    if not card_number:
        return None, None
    if "/" in card_number:
        a, b = card_number.split("/", 1)
        return normalize_number(a), normalize_number(b)
    return normalize_number(card_number), None


@dataclass
class ParsedTitle:
    raw: str
    folded: str
    number: str | None = None
    total: str | None = None
    set_code: str | None = None
    set_name: str | None = None
    product_type: str | None = None
    is_lot: bool = False
    language: str = "en"
    grade_company: str | None = None
    grade: float | None = None
    condition: str | None = None
    tokens: list[str] = field(default_factory=list)


def parse_title(title: str, sets: SetsConfig) -> ParsedTitle:
    folded = fold(title)
    p = ParsedTitle(raw=title, folded=folded)
    padded = f" {folded} "

    if m := _NUMBER.search(title):
        p.number, p.total = normalize_number(m.group(1)), normalize_number(m.group(2))
    elif m := _PROMO.search(title):
        p.number = normalize_number(m.group(1) + m.group(2))
    elif m := _HASH_NUMBER.search(title):
        p.number = normalize_number(m.group(1))

    # Set by alias (longest alias first to prefer "paldea evolved" over "pal").
    best: tuple[int, str, str] | None = None
    for s in sets.sets:
        for alias in [s.name, *s.aliases]:
            a = fold(alias)
            # Short aliases ("pal", "151") must match as whole words.
            hit = (re.search(rf"(?<![\w]){re.escape(a)}(?![\w])", folded) is not None) if len(a) <= 3 else a in folded
            if hit and (best is None or len(a) > best[0]):
                best = (len(a), s.code, s.name)
    # Fall back to printed total → set (e.g. "177/162" → Temporal Forces).
    if best is None and p.total and p.total.isdigit():
        for s in sets.sets:
            if s.printed_total == int(p.total):
                best = (0, s.code, s.name)
                break
    if best:
        p.set_code, p.set_name = best[1], best[2]

    if not p.number:
        for ptype, words in PRODUCT_KEYWORDS:
            if any(w in padded for w in words):
                p.product_type = ptype
                break
    p.is_lot = any(w in padded for w in LOT_KEYWORDS) and not p.number
    if p.is_lot and p.product_type == "collection_box" and "box" not in folded and "boks" not in folded:
        p.product_type = None
    if any(j in padded for j in JAPANESE):
        p.language = "ja"
    if m := _GRADE.search(title):
        p.grade_company, p.grade = m.group(1).upper(), float(m.group(2))
    for word, cond in sorted(CONDITION_WORDS.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"(?<![\w]){re.escape(word)}(?![\w])", folded):
            p.condition = cond
            break
    p.tokens = re.findall(r"[a-z0-9\-]+", folded)
    return p

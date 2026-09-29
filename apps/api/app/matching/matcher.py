"""Card / product matching with explicit confidence.

Confidence bands: >=0.90 auto-match, 0.70–0.89 needs review, <0.70 unresolved.
We never silently accept a low-confidence match.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import SetsConfig
from app.db.models import Card, EntityType, MatchStatus, Product
from app.matching.normalize import ParsedTitle, fold, parse_title, split_card_number

AUTO_THRESHOLD = 0.90
REVIEW_THRESHOLD = 0.70


@dataclass
class Candidate:
    entity_type: str
    entity_id: int
    label: str
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    entity_type: str | None
    entity_id: int | None
    confidence: float
    status: str
    parsed: ParsedTitle
    candidates: list[Candidate] = field(default_factory=list)

    def candidates_json(self) -> list[dict]:
        return [{"entity_type": c.entity_type, "entity_id": c.entity_id, "label": c.label,
                 "score": round(c.score, 3), "reasons": c.reasons} for c in self.candidates[:5]]


def status_for(confidence: float) -> str:
    if confidence >= AUTO_THRESHOLD:
        return MatchStatus.AUTO
    if confidence >= REVIEW_THRESHOLD:
        return MatchStatus.REVIEW
    return MatchStatus.UNRESOLVED


def _name_similarity(parsed: ParsedTitle, name: str) -> float:
    return fuzz.token_set_ratio(fold(name), parsed.folded) / 100.0


def score_card(parsed: ParsedTitle, card: Card) -> Candidate:
    reasons: list[str] = []
    score = 0.0
    num, total = split_card_number(card.card_number)
    if parsed.number and num and parsed.number == num:
        if parsed.total and total:
            if parsed.total == total:
                score += 0.45
                reasons.append("number+total match")
            else:
                score -= 0.2
                reasons.append("printed total mismatch")
        else:
            score += 0.3
            reasons.append("number match")
    elif parsed.number and num:
        score -= 0.3
        reasons.append("number mismatch")

    if parsed.set_code and card.set_code:
        if parsed.set_code.lower() == card.set_code.lower():
            score += 0.2
            reasons.append("set match")
        else:
            score -= 0.25
            reasons.append("set mismatch")

    poke = card.pokemon_name or card.name
    poke_sim = _name_similarity(parsed, poke)
    name_sim = _name_similarity(parsed, card.name)
    sim = max(poke_sim, name_sim)
    score += 0.35 * sim
    reasons.append(f"name similarity {sim:.2f}")

    if parsed.language != (card.language or "en"):
        score -= 0.3
        reasons.append("language mismatch")
    return Candidate(EntityType.CARD, card.id, f"{card.name} {card.card_number or ''} ({card.set_name})",
                     max(0.0, min(1.0, score)), reasons)


def score_product(parsed: ParsedTitle, product: Product) -> Candidate:
    reasons: list[str] = []
    score = 0.0
    if parsed.product_type and parsed.product_type == product.product_type:
        score += 0.35
        reasons.append("product type match")
    elif parsed.product_type:
        score -= 0.3
        reasons.append("product type mismatch")
    if parsed.set_code and product.set_code:
        if parsed.set_code.lower() == product.set_code.lower():
            score += 0.35
            reasons.append("set match")
        else:
            score -= 0.3
            reasons.append("set mismatch")
    sim = _name_similarity(parsed, product.name)
    score += 0.3 * sim
    reasons.append(f"name similarity {sim:.2f}")
    if parsed.language != (product.language or "en"):
        score -= 0.3
        reasons.append("language mismatch")
    return Candidate(EntityType.PRODUCT, product.id, product.name, max(0.0, min(1.0, score)), reasons)


def _card_candidates(session: Session, parsed: ParsedTitle) -> list[Card]:
    q = select(Card)
    filters = []
    if parsed.number:
        # card_number stored like "177/162" or "177"; prefilter loosely then score precisely
        filters.append(Card.card_number.like(f"%{parsed.number.lstrip('0')}%"))
    if parsed.set_code:
        filters.append(Card.set_code == parsed.set_code)
    if filters:
        q = q.where(or_(*filters))
    rows = list(session.scalars(q.limit(2000)).all())
    if not rows and parsed.tokens:
        like = [Card.name.ilike(f"%{t}%") for t in parsed.tokens if len(t) >= 4][:6]
        if like:
            rows = list(session.scalars(select(Card).where(or_(*like)).limit(500)).all())
    return rows


def match_listing(session: Session, title: str, sets: SetsConfig) -> MatchResult:
    parsed = parse_title(title, sets)
    cands: list[Candidate] = []
    if parsed.is_lot:
        return MatchResult(None, None, 0.0, MatchStatus.UNRESOLVED, parsed, [])
    if parsed.product_type and not parsed.number:
        q = select(Product)
        if parsed.set_code:
            q = q.where(or_(Product.set_code == parsed.set_code, Product.product_type == parsed.product_type))
        else:
            q = q.where(Product.product_type == parsed.product_type)
        cands = [score_product(parsed, p) for p in session.scalars(q.limit(500)).all()]
    else:
        cands = [score_card(parsed, c) for c in _card_candidates(session, parsed)]
    cands.sort(key=lambda c: c.score, reverse=True)
    if not cands:
        return MatchResult(None, None, 0.0, MatchStatus.UNRESOLVED, parsed, [])
    best = cands[0]
    confidence = best.score
    # Ambiguity guard: two near-identical candidates can never auto-match.
    if len(cands) > 1 and cands[1].score >= best.score - 0.05:
        confidence = min(confidence, AUTO_THRESHOLD - 0.01)
        best.reasons.append("ambiguous: close runner-up")
    status = status_for(confidence)
    if status == MatchStatus.UNRESOLVED:
        return MatchResult(None, None, round(confidence, 3), status, parsed, cands)
    return MatchResult(best.entity_type, best.entity_id, round(confidence, 3), status, parsed, cands)

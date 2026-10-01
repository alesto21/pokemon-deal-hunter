"""Configurable deal-scoring engine (pure: no DB, no network)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import UserConfig
from app.db.models import Recommendation
from app.matching.normalize import fold
from app.portfolio.modifiers import portfolio_modifier
from app.portfolio.service import name_in
from app.pricing.grading import GradingEconomics, grading_economics
from app.pricing.sealed import SealedAnalysis, analyse_sealed
from app.pricing.stats import interpolate
from app.scoring.context import EvaluationContext


@dataclass
class ScoreResult:
    total_score: float
    recommendation: str
    discount_pct: float | None                # landed cost vs fair value (drives score + alerts)
    components: dict[str, float]              # 0..1 per component
    weighted: dict[str, float]                # points per component
    modifiers: dict[str, float]               # points added/subtracted
    seller_confidence: float
    portfolio_points: float
    binder_fit: str
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    grading: GradingEconomics | None = None
    sealed: SealedAnalysis | None = None
    item_discount_pct: float | None = None    # item price alone vs fair value (sanity checks only)
    shipping_basis: str = "exact"             # copied from the context for the level guard
    landed_cost_confidence: float = 1.0

    def to_json(self) -> dict[str, Any]:
        return {
            "components": self.components,
            "weighted": self.weighted,
            "modifiers": self.modifiers,
            "reasons": self.reasons,
            "warnings": self.warnings,
            "binder_fit": self.binder_fit,
            "item_discount_pct": self.item_discount_pct,
            "shipping_basis": self.shipping_basis,
            "landed_cost_confidence": self.landed_cost_confidence,
            "grading": self.grading.__dict__ if self.grading else None,
            "sealed": self.sealed.__dict__ if self.sealed else None,
        }


def recommendation_for(score: float, bands: dict[str, float]) -> str:
    for rec in ("STEAL", "STRONG_BUY", "GOOD", "WATCH"):
        if score >= bands.get(rec, 101):
            return rec
    return Recommendation.IGNORE


def popularity_score(pokemon: str | None, cfg: UserConfig) -> tuple[float, str | None]:
    best, tier_name = cfg.pokemon.default_score, None
    for name, tier in cfg.pokemon.popularity_tiers.items():
        if tier.score > best and name_in(tier.names, pokemon):
            best, tier_name = tier.score, name
    return best, tier_name


def binder_fit(ctx: EvaluationContext, cfg: UserConfig) -> str:
    if ctx.entity_type == "product" or ctx.listing_kind == "sealed":
        return "sealed"
    if ctx.listing_kind == "graded":
        return "graded"
    fv = ctx.fair_value.fair_value_nok if ctx.fair_value else None
    if ctx.is_premium_target or (fv and fv >= cfg.binders.premium["min_raw_value_nok"]):
        return "premium"
    if (fv and fv >= cfg.binders.regular["min_raw_value_nok"]) or cfg.rarities.is_premium(ctx.rarity):
        return "regular"
    return "none"


def seller_confidence(ctx: EvaluationContext, cfg: UserConfig) -> tuple[float, list[str]]:
    base = {"cardtrader": 0.9, "store": 0.9, "finn": 0.7, "manual": 0.7, "ebay": 0.75}
    source_key = "store" if ctx.source.startswith("store:") else ctx.source
    score = base.get(source_key, 0.6)
    notes: list[str] = []
    if ctx.seller_verified:
        score = max(score, 0.95)
    if ctx.seller_rating is not None:
        score = 0.5 * score + 0.5 * ctx.seller_rating
    text = fold(f"{ctx.title} {ctx.description or ''}")
    flags = [w for w in cfg.scoring.red_flags if re.search(rf"(?<!\w){re.escape(fold(w))}(?!\w)", text)]
    if flags:
        score *= 0.4
        notes.append(f"red-flag words: {', '.join(flags)}")
    return round(max(0.0, min(1.0, score)), 3), notes


def score_listing(ctx: EvaluationContext, cfg: UserConfig) -> ScoreResult:
    sc = cfg.scoring
    w = sc.weights
    comps: dict[str, float] = {}
    mods: dict[str, float] = {}
    reasons: list[str] = []
    warnings: list[str] = []

    fv = ctx.fair_value
    fair = fv.fair_value_nok if fv else None
    if not fair:
        return ScoreResult(0, Recommendation.IGNORE, None, {}, {}, {}, 0, 0, "none",
                           [], ["no fair value available — cannot score"])
    discount = (fair - ctx.total_price_nok) / fair  # total_price_nok = landed cost
    item_price = ctx.listing_price_nok if ctx.listing_price_nok is not None else ctx.total_price_nok
    # "Too good to be true" is judged on the item price: shipping/import dilute the discount of
    # cheap cards and would hide a suspicious listing.
    item_discount = (fair - item_price) / fair

    # --- components (0..1)
    comps["discount_to_fair_value"] = interpolate(sc.discount_curve, discount) * (0.5 + 0.5 * fv.confidence)
    comps["liquidity"] = interpolate(sc.liquidity_curve, ctx.listing_count)
    set_meta = cfg.sets.find(ctx.set_code) or cfg.sets.find(ctx.set_name)
    set_des = set_meta.desirability if set_meta else cfg.sets.default_desirability
    comps["set_desirability"] = set_des
    if ctx.entity_type == "product":
        comps["pokemon_popularity"] = 0.5 + 0.5 * set_des
    else:
        comps["pokemon_popularity"], tier = popularity_score(ctx.pokemon_name or ctx.entity_name, cfg)
        if tier == "iconic":
            reasons.append("iconic Pokémon")
        elif tier == "high":
            reasons.append("high-demand Pokémon")
    trend = ctx.history.trend_30d
    comps["trend"] = interpolate(sc.trend_curve, trend) if trend is not None else sc.unknown_trend_score

    grading: GradingEconomics | None = None
    sealed: SealedAnalysis | None = None
    if ctx.entity_type == "product":
        sealed = analyse_sealed(ctx.total_price_nok, ctx.pack_count, ctx.loose_pack_value_nok, fair,
                                ctx.release_date, set_des, ctx.top_chase_value_nok, trend)
        # For sealed the "grading upside" slot measures long-term sealed-hold attractiveness.
        comps["grading_upside"] = sealed.sealed_investment_score
        comps["scarcity"] = min(1.0, 0.3 + (sealed.product_age_years or 0) / 5)
    else:
        grading = grading_economics(fair, ctx.psa9_nok, ctx.psa10_nok, cfg.grading)
        comps["grading_upside"] = grading.score if grading.score is not None else sc.unknown_grading_score
        if grading.label == "Strong":
            reasons.append("strong PSA10 grading upside")
        warnings.extend(grading.flags)
        rarity_scarcity = cfg.rarities.scarcity_for(ctx.rarity)
        supply = interpolate([(1, 1.0), (5, 0.6), (20, 0.2), (50, 0.0)], max(ctx.listing_count, 1))
        comps["scarcity"] = 0.7 * rarity_scarcity + 0.3 * supply

    comps = {k: round(max(0.0, min(1.0, v)), 4) for k, v in comps.items()}
    weighted = {k: round(comps.get(k, 0) * w.get(k, 0), 2) for k in w}
    base = sum(weighted.values())

    # --- modifiers (points)
    fit = binder_fit(ctx, cfg)
    pm = portfolio_modifier(ctx.portfolio, discount, fit, cfg.binders.modifiers)
    if pm.points:
        mods["portfolio"] = pm.points
    reasons.extend(pm.reasons)

    seller_conf, seller_notes = seller_confidence(ctx, cfg)
    warnings.extend(seller_notes)
    m = sc.modifiers
    if seller_conf < m.seller_confidence_neutral:
        shortfall = (m.seller_confidence_neutral - seller_conf) / m.seller_confidence_neutral
        mods["seller_confidence"] = -round(m.seller_confidence_max_penalty * shortfall, 2)

    if ctx.match_confidence < 0.9:
        mods["match_confidence"] = -round((0.9 - ctx.match_confidence) * 10 * m.match_confidence_penalty_per_0_1, 2)
        warnings.append(f"identity match confidence {ctx.match_confidence:.2f}")
    if ctx.listing_kind == "lot":
        mods["lot_uncertainty"] = -m.lot_uncertainty_penalty
        warnings.append("lot valuation is uncertain")
    elif ctx.quantity > 1:
        mods["multi_item_bundle"] = -m.multi_item_bundle_penalty

    if ctx.watchlist_target_nok and ctx.total_price_nok <= ctx.watchlist_target_nok:
        mods["watchlist_target_met"] = m.watchlist_target_met_bonus
        reasons.append(f"at/below your watchlist target ({ctx.watchlist_target_nok:.0f} NOK)")
    if ctx.watchlist_priority == "high":
        mods["watchlist_high_priority"] = m.watchlist_high_priority_bonus
    if fit == "premium" and fair >= cfg.binders.premium["min_raw_value_nok"]:
        mods["premium_value"] = m.premium_value_bonus
        if ctx.total_price_nok > cfg.binders.premium["preferred_max_buy_nok"]:
            mods["premium_value"] = 0
            warnings.append("above preferred premium max buy price")

    total = round(max(0.0, min(100.0, base + sum(mods.values()))), 1)
    rec = recommendation_for(total, sc.bands)

    if item_discount >= cfg.alerts.suspicious_discount:
        warnings.insert(0, f"unusually cheap (item price {item_discount:.0%} below fair value) — verify "
                           "listing, condition and authenticity before buying")
    if discount > 0.02:
        reasons.append(f"price {discount:.0%} below fair value")
    elif discount < -0.02:
        warnings.append(f"price {abs(discount):.0%} above fair value")
    if comps["liquidity"] >= 0.7:
        reasons.append("liquid market (many active listings)")
    if trend is not None and trend >= 0.05:
        reasons.append(f"rising 30d trend ({trend:+.1%})")
    elif trend is not None and trend <= -0.05:
        warnings.append(f"falling 30d trend ({trend:+.1%})")
    if fv.confidence < 0.6:
        warnings.append(f"fair value confidence low ({fv.confidence:.2f})")
    if fit == "premium":
        reasons.append("fits premium binder")
    if ctx.is_premium_target:
        reasons.append("on your premium target list")

    if ctx.shipping_basis == "estimated":
        warnings.append("shipping estimate — verify at checkout")
    elif ctx.shipping_basis == "pickup":
        warnings.append("pickup required — not delivered; travel/meeting cost not included")
    return ScoreResult(total, rec, round(discount, 4), comps, weighted, mods, seller_conf, pm.points, fit,
                       reasons, warnings, grading, sealed, round(item_discount, 4), ctx.shipping_basis,
                       ctx.landed_cost_confidence)

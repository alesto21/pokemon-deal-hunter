"""Notification policy: hard filters, severity, duplicate/cooldown/daily-cap handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.core.config import UserConfig
from app.db.base import utcnow
from app.matching.normalize import fold
from app.portfolio.service import name_in
from app.pricing.landed_cost import region_allowed_for_deals
from app.scoring.context import EvaluationContext
from app.scoring.engine import ScoreResult

LEVELS = ["IGNORE", "WATCH", "GOOD", "STRONG_BUY", "STEAL"]


@dataclass
class PreviousAlert:
    sent_at: datetime
    price_nok: float | None


@dataclass
class AlertState:
    previous: PreviousAlert | None = None          # last alert for this listing
    previous_entity: PreviousAlert | None = None   # last alert for the same card/product (any listing)
    alerts_today: int = 0
    now: datetime | None = None


@dataclass
class Decision:
    notify: bool
    severity: str | None
    blocked_by: list[str] = field(default_factory=list)


def _dropped(prev: PreviousAlert, price: float, min_drop: float) -> bool:
    return bool(prev.price_nok and prev.price_nok > 0 and (prev.price_nok - price) / prev.price_nok >= min_drop)


def _threshold(level: str, cfg: UserConfig) -> float:
    a = cfg.alerts
    return {"STEAL": a.minimum_discount_steal, "STRONG_BUY": a.minimum_discount_strong_buy,
            "GOOD": a.minimum_discount_good}.get(level, 0.0)


def _discount_level(discount: float, cfg: UserConfig) -> str:
    a = cfg.alerts
    if discount >= a.minimum_discount_steal:
        return "STEAL"
    if discount >= a.minimum_discount_strong_buy:
        return "STRONG_BUY"
    if discount >= a.minimum_discount_good:
        return "GOOD"
    return "WATCH"


@dataclass
class EffectiveLevel:
    raw_band: str            # from the score alone
    level: str               # after the discount cap and the suspicious-price guard
    caps: list[str] = field(default_factory=list)


def effective_level(result: ScoreResult, cfg: UserConfig) -> EffectiveLevel:
    """The level a listing actually deserves after caps. Stateless: cooldowns, daily cap and hard
    filters decide *whether* to notify (see ``decide``), not the level itself."""
    a = cfg.alerts
    raw = result.recommendation
    discount = result.discount_pct or 0.0
    caps: list[str] = []
    level = LEVELS.index(raw)
    supported = _discount_level(discount, cfg)
    if LEVELS.index(supported) < level:
        level = LEVELS.index(supported)
        caps.append(f"landed discount {discount:.1%} supports at most {supported}")
    # Estimated shipping: STRONG_BUY/STEAL only if the discount clears its threshold with a margin
    # for the shipping uncertainty (cheap item != cheap delivered). Exact quotes need no margin.
    if result.shipping_basis == "estimated" and level >= LEVELS.index("STRONG_BUY"):
        margin = a.estimated_shipping_margin
        backed = _discount_level(discount - margin, cfg)
        if LEVELS.index(backed) < level:
            caps.append(f"shipping estimated — {LEVELS[level]} needs ≥ "
                        f"{_threshold(LEVELS[level], cfg) + margin:.0%} landed discount with estimated shipping "
                        f"(have {discount:.1%}); verify at checkout")
            level = LEVELS.index(backed)
    item_discount = result.item_discount_pct if result.item_discount_pct is not None else discount
    if item_discount >= a.suspicious_discount and level > LEVELS.index("STRONG_BUY"):
        level = LEVELS.index("STRONG_BUY")
        caps.append(f"suspicious-price guard: item price {item_discount:.0%} below fair value "
                    f"(≥ {a.suspicious_discount:.0%}) — capped at STRONG_BUY, verify listing")
    return EffectiveLevel(raw, LEVELS[level], caps)


def _good_rule_hit(ctx: EvaluationContext, result: ScoreResult, cfg: UserConfig) -> bool:
    rules = cfg.alerts.good_rules
    if rules.watchlist_target_met and "watchlist_target_met" in result.modifiers:
        return True
    if rules.high_priority_missing and ctx.portfolio.is_high_priority and ctx.portfolio.owned_quantity == 0:
        return True
    return bool(rules.premium_binder_fit and result.binder_fit == "premium")


def decide(ctx: EvaluationContext, result: ScoreResult, state: AlertState, cfg: UserConfig) -> Decision:
    a = cfg.alerts
    blocked: list[str] = []
    fair = ctx.fair_value.fair_value_nok if ctx.fair_value else None
    discount = result.discount_pct or 0.0

    # Severity = score band capped by the landed discount and the suspicious-price guard.
    severity = effective_level(result, cfg).level
    if severity in ("IGNORE", "WATCH"):
        if result.recommendation in ("IGNORE", "WATCH"):
            return Decision(False, severity, [f"score {result.total_score:.0f} is {result.recommendation}"])
        return Decision(False, severity, [f"discount {discount:.1%} below the {a.minimum_discount_good:.0%} "
                                          f"minimum for an alert (score says {result.recommendation})"])
    if severity == "GOOD" and not _good_rule_hit(ctx, result, cfg):
        blocked.append("GOOD without special rule (watchlist target / high-priority missing / premium fit)")

    if ctx.market_conflict:
        blocked.append(f"market_data_conflict: {ctx.market_conflict}")
    if ctx.listing_kind == "lot":
        cov = ctx.lot_coverage
        if cov is None:
            blocked.append("lot: total item count unknown — value coverage cannot be established")
        elif cov < a.lot_min_coverage:
            blocked.append(f"lot: only {cov:.0%} of items identified (< {a.lot_min_coverage:.0%}); "
                           f"{ctx.lot_unidentified} unidentified")
    if ctx.seller_region is not None and not region_allowed_for_deals(ctx.seller_region, cfg.sources):
        blocked.append(f"seller_region_not_allowed ({ctx.seller_region}"
                       f"{', ' + ctx.seller_country if ctx.seller_country else ''})")
    high_priority_watch = ctx.watchlist_priority == "high"
    if not fair or (fair < a.minimum_notification_fair_value_nok and not high_priority_watch):
        blocked.append(f"fair value below {a.minimum_notification_fair_value_nok:.0f} NOK")
    if ctx.match_confidence < a.min_match_confidence:
        blocked.append(f"match confidence {ctx.match_confidence:.2f} < {a.min_match_confidence}")
    if ctx.fair_value and ctx.fair_value.confidence < a.min_fair_value_confidence:
        blocked.append(f"fair value confidence {ctx.fair_value.confidence:.2f} < {a.min_fair_value_confidence}")
    cond = fold(ctx.condition or "")
    if not a.allow_damaged and cond and any(fold(d) == cond for d in a.damaged_conditions):
        blocked.append(f"condition '{ctx.condition}' excluded")
    if name_in(cfg.pokemon.ignored, ctx.pokemon_name):
        blocked.append("Pokémon is on ignored list")
    if ctx.portfolio.owned_quantity > 0 and discount <= cfg.binders.modifiers.duplicate_exceptional_discount:
        blocked.append("duplicate of owned card without exceptional discount")
    if result.seller_confidence < 0.3:
        blocked.append("seller/listing confidence too low")

    now = state.now or utcnow()
    if state.previous:
        prev = state.previous
        cooled = now - prev.sent_at >= timedelta(hours=a.repeat_cooldown_hours)
        if not (cooled and _dropped(prev, ctx.total_price_nok, a.repeat_min_price_drop)):
            blocked.append("already alerted (cooldown / no meaningful price drop)")
    elif state.previous_entity:
        prev = state.previous_entity
        recent = now - prev.sent_at < timedelta(hours=a.repeat_cooldown_hours)
        if recent and not _dropped(prev, ctx.total_price_nok, a.repeat_min_price_drop):
            blocked.append("same card alerted recently at a similar or lower price")
    steal_exempt = severity == "STEAL" and a.steal_ignores_daily_cap
    if state.alerts_today >= a.max_alerts_per_day and not steal_exempt:
        blocked.append(f"daily alert cap ({a.max_alerts_per_day}) reached")

    return Decision(not blocked, severity, blocked)

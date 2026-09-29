"""Notification policy: hard filters, severity, duplicate/cooldown/daily-cap handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.core.config import UserConfig
from app.db.base import utcnow
from app.matching.normalize import fold
from app.portfolio.service import name_in
from app.scoring.context import EvaluationContext
from app.scoring.engine import ScoreResult

LEVELS = ["IGNORE", "WATCH", "GOOD", "STRONG_BUY", "STEAL"]


@dataclass
class PreviousAlert:
    sent_at: datetime
    price_nok: float | None


@dataclass
class AlertState:
    previous: PreviousAlert | None = None
    alerts_today: int = 0
    now: datetime | None = None


@dataclass
class Decision:
    notify: bool
    severity: str | None
    blocked_by: list[str] = field(default_factory=list)


def _discount_level(discount: float, cfg: UserConfig) -> str:
    a = cfg.alerts
    if discount >= a.minimum_discount_steal:
        return "STEAL"
    if discount >= a.minimum_discount_strong_buy:
        return "STRONG_BUY"
    if discount >= a.minimum_discount_good:
        return "GOOD"
    return "WATCH"


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

    # Severity = min(score band, band supported by the raw discount).
    level = min(LEVELS.index(result.recommendation), LEVELS.index(_discount_level(discount, cfg)))
    severity = LEVELS[level]
    if severity in ("IGNORE", "WATCH"):
        return Decision(False, severity, [f"recommendation {severity}"])
    if severity == "GOOD" and not _good_rule_hit(ctx, result, cfg):
        blocked.append("GOOD without special rule (watchlist target / high-priority missing / premium fit)")

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
        dropped = (prev.price_nok is not None and prev.price_nok > 0 and
                   (prev.price_nok - ctx.total_price_nok) / prev.price_nok >= a.repeat_min_price_drop)
        if not (cooled and dropped):
            blocked.append("already alerted (cooldown / no meaningful price drop)")
    steal_exempt = severity == "STEAL" and a.steal_ignores_daily_cap
    if state.alerts_today >= a.max_alerts_per_day and not steal_exempt:
        blocked.append(f"daily alert cap ({a.max_alerts_per_day}) reached")

    return Decision(not blocked, severity, blocked)

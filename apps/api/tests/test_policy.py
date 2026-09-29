from __future__ import annotations

from datetime import datetime, timedelta

from app.scoring.engine import ScoreResult, score_listing
from app.scoring.policy import AlertState, PreviousAlert, decide

from .factories import make_ctx

NOW = datetime(2026, 9, 30, 12, 0)


def forced(result: ScoreResult, rec: str, score: float) -> ScoreResult:
    result.recommendation, result.total_score = rec, score
    return result


def test_obvious_steal_notifies(cfg):
    ctx = make_ctx("obvious_steal")
    d = decide(ctx, score_listing(ctx, cfg), AlertState(now=NOW), cfg)
    assert d.notify, d.blocked_by
    assert d.severity in ("STRONG_BUY", "STEAL")


def test_watch_and_ignore_never_notify(cfg):
    ctx = make_ctx("fair_price")
    d = decide(ctx, score_listing(ctx, cfg), AlertState(now=NOW), cfg)
    assert not d.notify


def test_cheap_card_blocked_by_min_fair_value(cfg):
    ctx = make_ctx("cheap_worthless")
    r = forced(score_listing(ctx, cfg), "STEAL", 95)
    d = decide(ctx, r, AlertState(now=NOW), cfg)
    assert not d.notify
    assert any("fair value below" in b for b in d.blocked_by)


def test_severity_capped_by_discount(cfg):
    ctx = make_ctx("obvious_steal", total_price_nok=740)  # ~18.7% discount
    r = forced(score_listing(ctx, cfg), "STEAL", 95)
    d = decide(ctx, r, AlertState(now=NOW), cfg)
    assert d.severity == "GOOD"


def test_good_requires_special_rule(cfg):
    ctx = make_ctx("fair_price", total_price_nok=160, fair_value=300)  # regular binder, not high priority
    r = forced(score_listing(ctx, cfg), "GOOD", 78)
    d = decide(ctx, r, AlertState(now=NOW), cfg)
    assert not d.notify and any("special rule" in b for b in d.blocked_by)
    cfg.alerts.good_rules.premium_binder_fit = True
    ctx2 = make_ctx("fair_price", total_price_nok=160, fair_value=300, watchlist_target_nok=200)
    r2 = forced(score_listing(ctx2, cfg), "GOOD", 78)
    assert decide(ctx2, r2, AlertState(now=NOW), cfg).notify


def test_low_match_confidence_blocks(cfg):
    ctx = make_ctx("low_confidence_match")
    r = forced(score_listing(ctx, cfg), "STEAL", 95)
    d = decide(ctx, r, AlertState(now=NOW), cfg)
    assert not d.notify and any("match confidence" in b for b in d.blocked_by)


def test_damaged_condition_blocked_unless_allowed(cfg):
    ctx = make_ctx("obvious_steal", condition="Damaged")
    r = score_listing(ctx, cfg)
    assert not decide(ctx, r, AlertState(now=NOW), cfg).notify
    cfg.alerts.allow_damaged = True
    assert decide(ctx, r, AlertState(now=NOW), cfg).notify


def test_duplicate_suppressed_unless_exceptional(cfg):
    ctx = make_ctx("duplicate")
    r = forced(score_listing(ctx, cfg), "STRONG_BUY", 88)
    d = decide(ctx, r, AlertState(now=NOW), cfg)
    assert not d.notify and any("duplicate" in b for b in d.blocked_by)
    ctx2 = make_ctx("duplicate", total_price_nok=280)  # ~40% discount → exceptional
    r2 = forced(score_listing(ctx2, cfg), "STEAL", 95)
    assert decide(ctx2, r2, AlertState(now=NOW), cfg).notify


def test_same_listing_not_resent(cfg):
    ctx = make_ctx("obvious_steal")
    r = score_listing(ctx, cfg)
    prev = PreviousAlert(NOW - timedelta(hours=2), 520)
    assert not decide(ctx, r, AlertState(previous=prev, now=NOW), cfg).notify
    # small price change after cooldown → still suppressed
    prev = PreviousAlert(NOW - timedelta(hours=30), 540)
    assert not decide(ctx, r, AlertState(previous=prev, now=NOW), cfg).notify
    # meaningful drop after cooldown → resend
    prev = PreviousAlert(NOW - timedelta(hours=30), 700)
    assert decide(ctx, r, AlertState(previous=prev, now=NOW), cfg).notify


def test_daily_cap_and_steal_exemption(cfg):
    ctx = make_ctx("obvious_steal")
    r = forced(score_listing(ctx, cfg), "STRONG_BUY", 88)
    capped = AlertState(alerts_today=cfg.alerts.max_alerts_per_day, now=NOW)
    assert not decide(ctx, r, capped, cfg).notify
    r_steal = forced(score_listing(ctx, cfg), "STEAL", 96)
    assert decide(ctx, r_steal, capped, cfg).notify


def test_ignored_pokemon_blocked(cfg):
    cfg.pokemon.ignored = ["Gastly"]
    ctx = make_ctx("obvious_steal")
    assert not decide(ctx, score_listing(ctx, cfg), AlertState(now=NOW), cfg).notify

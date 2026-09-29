from __future__ import annotations

from app.db.models import Recommendation
from app.scoring.engine import recommendation_for, score_listing

from .factories import make_ctx


def test_obvious_steal_scores_high(cfg):
    r = score_listing(make_ctx("obvious_steal"), cfg)
    assert r.discount_pct > 0.4
    assert r.recommendation in ("STRONG_BUY", "STEAL")
    assert r.binder_fit == "premium"
    assert any("below fair value" in x for x in r.reasons)


def test_fair_price_is_not_a_deal(cfg):
    r = score_listing(make_ctx("fair_price"), cfg)
    assert r.recommendation in (Recommendation.IGNORE, Recommendation.WATCH)


def test_overpriced_is_ignored(cfg):
    r = score_listing(make_ctx("overpriced"), cfg)
    assert r.discount_pct < 0
    assert r.recommendation == Recommendation.IGNORE
    assert any("above fair value" in w for w in r.warnings)


def test_cheap_worthless_card_is_ignored_even_with_30pct_discount(cfg):
    r = score_listing(make_ctx("cheap_worthless"), cfg)
    assert r.discount_pct >= 0.29
    assert r.recommendation in (Recommendation.IGNORE, Recommendation.WATCH)
    assert r.binder_fit == "none"


def test_duplicate_is_penalised(cfg):
    dup = score_listing(make_ctx("duplicate"), cfg)
    fresh = score_listing(make_ctx("duplicate", portfolio={"is_high_priority": True}), cfg)
    assert dup.modifiers["portfolio"] == cfg.binders.modifiers.duplicate_in_premium
    assert fresh.total_score > dup.total_score


def test_sealed_booster_box_gets_sealed_analysis(cfg):
    r = score_listing(make_ctx("sealed_booster_box"), cfg)
    assert r.binder_fit == "sealed"
    assert r.sealed is not None
    assert r.sealed.pack_count == 36
    assert r.sealed.price_per_pack_nok == round(1850 / 36, 2)
    assert r.grading is None


def test_low_confidence_match_is_penalised(cfg):
    low = score_listing(make_ctx("low_confidence_match"), cfg)
    high = score_listing(make_ctx("low_confidence_match", match_confidence=1.0), cfg)
    assert "match_confidence" in low.modifiers
    assert low.total_score < high.total_score


def test_red_flag_words_reduce_seller_confidence(cfg):
    clean = score_listing(make_ctx("obvious_steal"), cfg)
    flagged = score_listing(make_ctx("obvious_steal", title="Gastly 177/162 proxy custom card"), cfg)
    assert flagged.seller_confidence < clean.seller_confidence
    assert flagged.total_score < clean.total_score


def test_no_fair_value_means_ignore(cfg):
    ctx = make_ctx("fair_price")
    ctx.fair_value = None
    r = score_listing(ctx, cfg)
    assert r.recommendation == Recommendation.IGNORE and r.total_score == 0


def test_weights_are_configurable(cfg):
    base = score_listing(make_ctx("fair_price"), cfg).total_score
    cfg.scoring.weights["liquidity"] = 0
    assert score_listing(make_ctx("fair_price"), cfg).total_score < base


def test_watchlist_target_bonus(cfg):
    r = score_listing(make_ctx("fair_price", watchlist_target_nok=250), cfg)
    assert r.modifiers.get("watchlist_target_met") == cfg.scoring.modifiers.watchlist_target_met_bonus


def test_bands():
    bands = {"STEAL": 93, "STRONG_BUY": 85, "GOOD": 75, "WATCH": 60}
    assert recommendation_for(59.9, bands) == "IGNORE"
    assert recommendation_for(60, bands) == "WATCH"
    assert recommendation_for(80, bands) == "GOOD"
    assert recommendation_for(90, bands) == "STRONG_BUY"
    assert recommendation_for(99, bands) == "STEAL"

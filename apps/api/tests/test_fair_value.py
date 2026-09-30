"""Fair value = what a card can realistically be bought for. Scenarios run the full
raw prices → stats → fair value path."""

from __future__ import annotations

import pytest

from app.core.config import FairValueConfig
from app.pricing.fair_value import CurrentMarket, estimate_fair_value
from app.pricing.history import HistoryStats
from app.pricing.stats import compute_stats

CFG = FairValueConfig()
STABLE = HistoryStats(median_30d=100, days_30d=30, volatility_30d=0.02)


def market(prices: list[float]) -> CurrentMarket:
    s = compute_stats(prices, trim_fraction=CFG.trim_fraction, tail_ratio=CFG.tail_ratio,
                      low_outlier_ratio=CFG.low_outlier_ratio)
    return CurrentMarket(low=s.low, median=s.median, trimmed_median=s.trimmed_median,
                         cheapest5_median=s.cheapest5_median, listing_count=s.count, dispersion=s.dispersion,
                         cheapest3_median=s.cheapest3_median, cheapest10_median=s.cheapest10_median,
                         has_expensive_tail=s.has_expensive_tail, low_is_outlier=s.low_is_outlier)


def test_formula_with_history_is_60_25_15():
    cur = market([100, 100, 100, 100, 100, 120, 120, 120, 120, 120, 130, 140])
    fv = estimate_fair_value(cur, HistoryStats(median_30d=90, days_30d=30), CFG)
    assert cur.cheapest5_median == 100 and cur.cheapest10_median == 110
    assert fv.fair_value_nok == pytest.approx(0.60 * 100 + 0.25 * 110 + 0.15 * 90)


def test_without_history_cheapest5_and_10_dominate():
    cur = market([100, 100, 100, 100, 100, 120, 120, 120, 120, 120, 500, 600])
    fv = estimate_fair_value(cur, HistoryStats(), CFG)
    assert fv.fair_value_nok == pytest.approx((0.60 * 100 + 0.25 * 110) / 0.85, rel=1e-3)
    assert any("no own price history" in n for n in fv.explanation)


def test_normal_tight_market():
    cur = market([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111])
    fv = estimate_fair_value(cur, STABLE, CFG)
    assert 100 <= fv.fair_value_nok <= 105
    assert not cur.has_expensive_tail and not cur.low_is_outlier
    assert fv.confidence >= 0.9
    assert fv.flags == []


def test_large_overpriced_tail_is_flagged_and_ignored():
    prices = [80, 82, 84, 85, 86, 120, 125, 130, 140, 150, 160, 170, 200, 250, 300]
    cur = market(prices)
    fv = estimate_fair_value(cur, HistoryStats(), CFG)
    assert cur.has_expensive_tail
    assert "market_has_expensive_tail" in fv.flags
    assert fv.fair_value_nok < cur.trimmed_median * 0.8
    assert fv.fair_value_nok <= cur.cheapest10_median


def test_real_gastly_177_shape():
    """Live TEF Gastly 177 (EUR, valid NM English raw): 3 cheap asks, then a wall at ~115-165."""
    prices = [70.64, 78.34, 80.62, 115.67, 120.64, 122.10, 124.11, 128.82, 130.80, 134.00, 135.10,
              136.94, 137.17, 139.52, 145.54, 150.61, 164.24, 242.49]
    cur = market(prices)
    fv = estimate_fair_value(cur, HistoryStats(), CFG)
    assert cur.has_expensive_tail
    assert fv.fair_value_nok < cur.trimmed_median  # old model: ~109, trimmed median 128.8
    assert cur.cheapest5_median == 80.62 and cur.cheapest10_median == 121.37
    assert fv.fair_value_nok == pytest.approx((0.60 * 80.62 + 0.25 * 121.37) / 0.85, rel=1e-3)


def test_one_underpriced_outlier_does_not_define_fair_value():
    cur = market([40, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109])
    fv = estimate_fair_value(cur, STABLE, CFG)
    assert cur.low_is_outlier and "lowest_listing_outlier" in fv.flags
    assert fv.fair_value_nok >= 98


def test_one_overpriced_outlier_is_irrelevant():
    base = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
    a = estimate_fair_value(market(base), STABLE, CFG).fair_value_nok
    b = estimate_fair_value(market(base + [900]), STABLE, CFG).fair_value_nok
    assert b == pytest.approx(a, rel=0.01)


@pytest.mark.parametrize("prices", [[100], [100, 140]])
def test_one_or_two_listings_cannot_trigger_alerts(prices):
    fv = estimate_fair_value(market(prices), HistoryStats(), CFG)
    assert "thin_market" in fv.flags
    assert fv.confidence < 0.5  # below alerts.min_fair_value_confidence
    assert fv.fair_value_high - fv.fair_value_low > 0.3 * fv.fair_value_nok


def test_thin_market_leans_on_history():
    fv = estimate_fair_value(market([150, 160]), HistoryStats(median_30d=100, days_30d=20), CFG)
    assert fv.fair_value_nok == pytest.approx(0.6 * 155 + 0.4 * 100)


def test_volatile_market_lowers_confidence_and_widens_band():
    prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
    calm = estimate_fair_value(market(prices), STABLE, CFG)
    wild = estimate_fair_value(market(prices), HistoryStats(median_30d=100, days_30d=30, volatility_30d=0.3), CFG)
    assert wild.confidence < calm.confidence
    assert "volatile" in wild.flags
    assert (wild.fair_value_high - wild.fair_value_low) > (calm.fair_value_high - calm.fair_value_low)


def test_falling_market_capped_at_executable_price():
    cur = market([80, 80, 81, 81, 82, 82, 83, 83, 84, 84])
    fv = estimate_fair_value(cur, HistoryStats(median_30d=140, days_30d=30, trend_30d=-0.2), CFG)
    assert fv.fair_value_nok <= cur.cheapest5_median


def test_identity_uncertainty_lowers_confidence():
    cur = market([100, 101, 102, 103, 104, 105])
    assert estimate_fair_value(cur, STABLE, CFG, identity_confidence=0.7).confidence < \
        estimate_fair_value(cur, STABLE, CFG).confidence


def test_no_data():
    fv = estimate_fair_value(CurrentMarket(), HistoryStats(), CFG)
    assert fv.fair_value_nok is None and fv.confidence == 0

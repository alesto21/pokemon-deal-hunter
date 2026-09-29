from __future__ import annotations

from datetime import date, timedelta

import httpx
import pytest

from app.core.config import FairValueConfig, GradingConfig
from app.db.models import PriceDaily
from app.pricing.fair_value import CurrentMarket, estimate_fair_value
from app.pricing.fx import FxRates, get_rates, refresh_rates
from app.pricing.grading import grading_economics
from app.pricing.history import HistoryStats, compute_history_stats
from app.pricing.sealed import analyse_sealed
from app.pricing.stats import compute_stats, interpolate, trimmed_median


# ---------------------------------------------------------------- normalisation / FX
def test_fx_conversion_to_nok_and_between_currencies():
    fx = FxRates({"EUR": 11.5, "USD": 10.0})
    assert fx.to_nok(10, "eur") == 115.0
    assert fx.to_nok(100, "NOK") == 100.0
    assert fx.convert(115, "NOK", "EUR") == 10.0
    with pytest.raises(ValueError):
        fx.to_nok(1, "JPY")


def test_fx_refresh_is_cached_daily(session):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        return httpx.Response(200, json={"base": "NOK", "rates": {"EUR": 0.08, "USD": 0.1}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    rates = refresh_rates(session, client)
    assert rates.nok_per_unit["EUR"] == pytest.approx(12.5)
    refresh_rates(session, client)  # cached → no second request
    assert len(calls) == 1
    assert get_rates(session).to_nok(2, "USD") == 20.0


def test_fx_fallback_when_nothing_cached(session):
    rates = get_rates(session)
    assert rates.fallback is True
    assert rates.to_nok(1, "EUR") > 5


# ---------------------------------------------------------------- stats
def test_compute_stats_basic():
    prices = [100, 110, 105, 400, 98, 120, 102]
    s = compute_stats(prices, sellers=["a", "b", "a", "c", "d", "e", "f"])
    assert s.low == 98
    assert s.count == 7
    assert s.seller_count == 6
    assert s.cheapest5_median == 102  # median of 98,100,102,105,110
    assert s.trimmed_median < s.median or s.trimmed_median == s.median
    assert s.dispersion is not None


def test_trimmed_median_drops_expensive_outliers():
    assert trimmed_median([10, 11, 12, 13, 1000], 0.2) == 11.5


def test_compute_stats_empty():
    s = compute_stats([])
    assert s.count == 0 and s.low is None


def test_interpolate_clamps_and_interpolates():
    curve = [(0, 0), (0.2, 0.5), (0.4, 1)]
    assert interpolate(curve, -1) == 0
    assert interpolate(curve, 0.1) == pytest.approx(0.25)
    assert interpolate(curve, 1) == 1


# ---------------------------------------------------------------- fair value
FV = FairValueConfig()


def test_fair_value_is_not_just_the_cheapest_listing():
    cur = CurrentMarket(low=50, median=100, trimmed_median=98, cheapest5_median=90, listing_count=12, dispersion=0.2)
    fv = estimate_fair_value(cur, HistoryStats(), FV)
    assert fv.fair_value_nok == pytest.approx(0.6 * 98 + 0.4 * 90, rel=1e-3)
    assert fv.fair_value_nok > cur.low
    assert fv.fair_value_low < fv.fair_value_nok < fv.fair_value_high


def test_fair_value_blends_history():
    cur = CurrentMarket(trimmed_median=100, cheapest5_median=100, listing_count=12)
    hist = HistoryStats(median_30d=80, days_30d=20)
    fv = estimate_fair_value(cur, hist, FV)
    assert fv.fair_value_nok == pytest.approx(100 * 0.6 + 80 * 0.4)


def test_fair_value_confidence_drops_with_thin_dispersed_volatile_data():
    good = estimate_fair_value(CurrentMarket(trimmed_median=100, cheapest5_median=100, listing_count=15),
                               HistoryStats(median_30d=100, days_30d=30), FV)
    thin = estimate_fair_value(CurrentMarket(trimmed_median=100, cheapest5_median=100, listing_count=1),
                               HistoryStats(), FV)
    messy = estimate_fair_value(
        CurrentMarket(trimmed_median=100, cheapest5_median=100, listing_count=15, dispersion=0.9),
        HistoryStats(median_30d=100, days_30d=30, volatility_30d=0.3), FV, identity_confidence=0.8)
    assert good.confidence > thin.confidence
    assert good.confidence > messy.confidence
    assert messy.fair_value_high - messy.fair_value_low > good.fair_value_high - good.fair_value_low


def test_fair_value_falling_market_is_conservative():
    cur = CurrentMarket(trimmed_median=80, cheapest5_median=80, listing_count=10)
    fv = estimate_fair_value(cur, HistoryStats(median_30d=120, days_30d=30, trend_30d=-0.2), FV)
    assert fv.fair_value_nok == 80


def test_fair_value_without_data():
    fv = estimate_fair_value(CurrentMarket(), HistoryStats(), FV)
    assert fv.fair_value_nok is None and fv.confidence == 0


def test_history_stats_trend_and_windows():
    today = date.today()
    series = [PriceDaily(entity_type="card", entity_id=1, source="x", day=today - timedelta(days=29 - i),
                         median_price=100 + i, trimmed_median=100 + i, listing_count=10) for i in range(30)]
    h = compute_history_stats(series)
    assert h.median_7d > h.median_30d
    assert h.trend_30d > 0.15
    assert h.days_30d == 30


# ---------------------------------------------------------------- grading
def test_grading_upside_formula_and_flags():
    g = grading_economics(raw_value=900, psa9=1100, psa10=5300, cfg=GradingConfig())
    assert g.upside_psa10 == pytest.approx((5300 - 900 - 450) / 900, abs=1e-3)
    assert g.upside_psa9 < 0
    assert "PSA9 barely exceeds raw + grading cost" in g.flags
    assert "economics only work at PSA10" in g.flags


def test_grading_unknown_without_reference():
    assert grading_economics(500, None, None, GradingConfig()).score is None


def test_grading_not_recommended_when_psa10_close_to_raw():
    g = grading_economics(raw_value=1000, psa9=900, psa10=1300, cfg=GradingConfig())
    assert g.label == "None"


# ---------------------------------------------------------------- sealed
def test_sealed_normalisation_paradox_rift_example():
    s = analyse_sealed(2600, 36, loose_pack_value_nok=60, sealed_market_nok=2400,
                       release_date=date(2023, 11, 3), set_desirability=0.6, top_chase_value_nok=1500,
                       trend_30d=0.02)
    assert s.price_per_pack_nok == pytest.approx(72.22, abs=0.01)
    assert s.equivalent_pack_value_nok == 2160
    assert s.listing_vs_packs > 0  # more expensive than loose packs
    assert 0 <= s.rip_score <= 1 and 0 <= s.sealed_investment_score <= 1
    assert any("not an EV estimate" in n for n in s.notes)

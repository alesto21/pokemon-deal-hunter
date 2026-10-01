from __future__ import annotations

from datetime import date, timedelta

import httpx
import pytest

from app.core.config import GradingConfig
from app.db.models import PriceDaily
from app.pricing.fx import FxRates, get_rates, refresh_rates
from app.pricing.grading import grading_economics
from app.pricing.history import compute_history_stats
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
    assert s.cheapest3_median == 100
    assert s.cheapest5_median == 102  # median of 98,100,102,105,110
    assert s.cheapest10_median is None  # fewer than 10 listings
    assert s.trimmed_median <= s.median
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


# ---------------------------------------------------------------- history
def test_history_stats_trend_and_windows():
    today = date.today()
    series = [PriceDaily(entity_type="card", entity_id=1, source="x", day=today - timedelta(days=29 - i),
                         median_price=500, trimmed_median=500, cheapest5_median=100 + i, listing_count=10)
              for i in range(30)]
    h = compute_history_stats(series)
    assert h.median_7d > h.median_30d
    assert h.trend_30d > 0.15
    assert h.days_30d == 30
    assert h.median_30d < 150  # history is built from the executable (cheapest-5) price, not the tail


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


@pytest.mark.parametrize("tz", ["Etc/GMT-14", "Etc/GMT+12"])  # UTC+14 and UTC-12: at any hour one differs
def test_daily_aggregation_uses_utc_day_regardless_of_local_timezone(engine, monkeypatch, tz):
    """Regression: containers run in Europe/Oslo; aggregating date.today() missed UTC snapshots."""
    import time as _time
    from datetime import UTC, datetime

    from sqlalchemy import select as _select

    from app.db.session import session_scope
    from app.services import scan

    monkeypatch.setenv("TZ", tz)
    _time.tzset()
    try:
        assert scan.run_collector("cardtrader", send_alerts=False)["ok"]
        with session_scope() as s:
            days = {d.day for d in s.scalars(_select(PriceDaily)).all()}
        assert days == {datetime.now(UTC).date()}
    finally:
        monkeypatch.undo()
        _time.tzset()

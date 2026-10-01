"""Dashboard read models: correct aggregation and no fabricated data."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.main import create_app
from app.db.base import utc_today
from app.db.models import Card, GradedPriceReference, PortfolioItem, PortfolioSnapshot, PriceDaily, Product
from app.db.session import session_scope
from app.services import scan

P = "/api/v1/dashboard"


@pytest.fixture()
def client(engine):
    scan.run_collector("cardtrader", send_alerts=False)  # mock market data
    return TestClient(create_app())


def _card(number: str) -> int:
    with session_scope() as s:
        return s.scalar(select(Card.id).where(Card.card_number == number))


def _product(name: str) -> int:
    with session_scope() as s:
        return s.scalar(select(Product.id).where(Product.name == name))


def _add(**kw) -> None:
    with session_scope() as s:
        s.add(PortfolioItem(**kw))


def test_empty_portfolio_has_empty_states_not_zeros_passed_off_as_history(client):
    body = client.get(f"{P}/overview").json()
    assert body["portfolio"]["summary"]["item_count"] == 0
    assert body["portfolio"]["history"] == {"points": [], "ready": False,
                                            "message": "History is being collected — one snapshot per day."}
    assert body["portfolio"]["allocation"] == []
    assert body["portfolio"]["top_performers"] == [] and body["portfolio"]["largest_positions"] == []
    assert body["kpis"]["active_listings"] > 0


def test_overview_best_deals_use_effective_level(client):
    body = client.get(f"{P}/overview").json()
    for d in body["best_deals"]:
        assert d["level"] in ("GOOD", "STRONG_BUY", "STEAL")
        p = d["price"]
        assert p["landed_nok"] == pytest.approx(p["item_nok"] + p["shipping_nok"] + p["import_buffer_nok"], abs=0.02)
        assert d["discount_nok"] == pytest.approx(d["fair_value_nok"] - p["landed_nok"], abs=0.02)
        assert d["entity"]["image_url"] is None or d["entity"]["image_url"].startswith("http")


def test_portfolio_kinds_allocation_and_history(client):
    gastly, pikachu = _card("177/162"), _card("173/165")
    _add(card_id=gastly, acquisition_price_nok=600, binder_type="premium")
    _add(card_id=pikachu, acquisition_price_nok=150, binder_type="graded", grading_status="graded", psa_grade=10)
    _add(product_id=_product("Paradox Rift Booster Box"), acquisition_price_nok=1800, binder_type="sealed")
    with session_scope() as s:
        s.add(GradedPriceReference(card_id=pikachu, grade=10, price_nok=900, source="manual"))
        s.add(PortfolioSnapshot(day=date.today() - timedelta(days=1), total_cost_nok=600, raw_value_nok=700,
                                graded_value_nok=0, by_binder={}))
    body = client.get(f"{P}/portfolio").json()
    kinds = body["by_kind"]
    assert kinds["raw"]["count"] == 1 and kinds["graded"]["count"] == 1 and kinds["sealed"]["count"] == 1
    assert kinds["graded"]["value_nok"] == 900  # graded reference, never the raw price
    assert {a["kind"] for a in body["allocation"]} == {"raw", "graded", "sealed"}
    assert body["history"]["ready"] is False  # one real snapshot is not a history
    assert len(body["largest_positions"]) == 3
    assert len(body["holdings"]) == 3 and all(h["added_at"] for h in body["holdings"])


def test_god_binder_slots_and_rows(client):
    gastly = _card("177/162")
    _add(card_id=gastly, acquisition_price_nok=600, binder_type="premium", quantity=2)
    _add(card_id=_card("199/165"), acquisition_price_nok=1200, binder_type="regular")
    body = client.get(f"{P}/binder/premium").json()
    assert body["capacity"] == 216 and body["slots_used"] == 2 and body["slots_free"] == 214
    assert body["pct_complete"] == pytest.approx(2 / 216, abs=1e-4)
    item = body["items"][0]
    assert item["entity"]["number"] == "177/162" and item["quantity"] == 2
    assert item["gain_nok"] == pytest.approx(item["value_nok"] - 1200, abs=0.02)
    assert body["sets"] == [{"set_name": "Temporal Forces", "cards": 2}]
    assert client.get(f"{P}/binder/regular").json()["capacity"] == 360
    assert client.get(f"{P}/binder/nope").status_code == 404


def test_sealed_pack_math(client):
    box = _product("Paradox Rift Booster Box")
    _add(product_id=box, acquisition_price_nok=1800, binder_type="sealed", quantity=2)
    body = client.get(f"{P}/sealed").json()
    row = body["items"][0]
    assert row["packs"] == 72 and row["nok_per_pack_acquired"] == 50.0
    assert row["nok_per_pack_now"] == pytest.approx(row["unit_value_nok"] / 36, abs=0.01)
    assert set(row["analysis"]) >= {"rip_score", "hold_score"}
    assert body["summary"]["products"] == 1 and body["summary"]["total_packs"] == 72


def test_grading_missing_references_are_flagged_not_invented(client):
    gastly, raichu = _card("177/162"), _card("211/193")
    _add(card_id=gastly, acquisition_price_nok=600, binder_type="premium")
    _add(card_id=raichu, acquisition_price_nok=150, binder_type="regular", grading_status="at_grader")
    with session_scope() as s:
        s.add(GradedPriceReference(card_id=gastly, grade=10, price_nok=5300, source="manual"))
    body = client.get(f"{P}/grading").json()
    cand = body["candidates"][0]
    assert cand["psa9"] is None and cand["psa9_net_nok"] is None
    assert "PSA 9 reference" in cand["missing"]
    assert cand["psa10"]["price_nok"] == 5300
    assert cand["psa10_net_nok"] == pytest.approx(5300 - cand["raw_value_nok"] - 450, abs=0.02)
    assert body["counts"] == {"candidates": 1, "submitted": 0, "at_grader": 1, "returned": 0}


def test_watchlist_enrichment(client):
    gastly = _card("177/162")
    client.post("/api/v1/watchlist", json={"entity_id": gastly, "target_buy_price": 700, "priority": "high"})
    item = client.get(f"{P}/watchlist").json()["items"][0]
    assert item["entity"]["number"] == "177/162" and item["fair_value_nok"] > 0
    assert item["market"]["valid_listings"] > 0
    best = item["best_listing"]
    assert best is not None and item["below_target"] == (best["price"]["landed_nok"] <= 700)


def test_market_movers_need_two_days_of_real_history(client):
    body = client.get(f"{P}/market").json()
    assert body["coverage"]["days_collected"] == 1  # only today's aggregate exists
    assert body["movers_ready"] is False and body["gainers"] == [] and body["decliners"] == []
    assert body["coverage"]["observations"] > 0 and body["most_liquid"]
    gastly = _card("177/162")
    with session_scope() as s:  # add a real earlier aggregate → now a mover exists
        today = s.scalar(select(PriceDaily).where(PriceDaily.entity_id == gastly, PriceDaily.entity_type == "card"))
        s.add(PriceDaily(entity_type="card", entity_id=gastly, source="cardtrader", day=utc_today() - timedelta(days=3),
                         cheapest5_median=today.cheapest5_median / 1.25, samples=1))
    body = client.get(f"{P}/market").json()
    assert body["movers_ready"] and body["gainers"][0]["entity_id"] == gastly
    assert body["gainers"][0]["change_pct"] == pytest.approx(0.25, abs=0.001)


def test_market_series_uses_only_collected_days(client):
    series = client.get(f"{P}/market/series/card/{_card('177/162')}").json()
    assert series["history_ready"] is False and len(series["daily"]) == 1
    assert series["daily"][0]["fair_value"] is not None  # median of stored evaluations that day
    assert series["intraday"] and series["current"]["cheapest5"]


def test_deals_filters_and_detail(client):
    body = client.get(f"{P}/deals", params={"level": ["GOOD", "STRONG_BUY", "STEAL"]}).json()
    assert all(d["level"] in ("GOOD", "STRONG_BUY", "STEAL") for d in body["items"])
    assert client.get(f"{P}/deals", params={"seller_region": "US"}).json()["total"] == 0  # mock sellers are EEA
    lid = client.get(f"{P}/deals", params={"pokemon": "gastly"}).json()["items"][0]["listing_id"]
    detail = client.get(f"{P}/deals/{lid}").json()
    assert detail["market"]["cheapest5"] and detail["market"]["valid_listings"] > 0
    assert set(detail["price"]) >= {"item_nok", "shipping_nok", "import_buffer_nok", "landed_nok"}
    assert "caps" in detail and "raw_band" in detail and detail["level"]
    assert client.get(f"{P}/deals/999999").status_code == 404


def test_alerts_and_system(client):
    body = client.get(f"{P}/alerts").json()
    assert set(body["summary"]) >= {"today", "window", "by_level", "live", "dry_run", "blocked"}
    sysinfo = client.get(f"{P}/system").json()
    assert sysinfo["database"]["ok"] is True
    assert sysinfo["telegram"]["mode"] == "dry-run" and sysinfo["telegram"]["configured"] is False
    assert sysinfo["backups"] == {"configured": False}
    assert sysinfo["worker"]["lock"]["locked"] is False
    assert sysinfo["overall_ok"] is False  # no worker has scheduled a scan in this test


    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k.lower()
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)

    secret_words = ("token", "api_key", "password", "secret", "chat_id")
    assert not [k for k in keys(sysinfo) if any(w in k for w in secret_words)]  # no secret fields exposed


def test_strongest_discounts_exclude_untrustworthy_fair_values(client):
    """Live case: 2-listing thin market with a placeholder ask → fair value 54k NOK, confidence 0.36."""
    from app.db.models import DealEvaluation, Listing

    with session_scope() as s:
        listing = Listing(source="cardtrader", external_id="thin-1", title="Mini Tin", asking_price=20, currency="EUR",
                          normalized_price_nok=221, total_price_nok=301, landed_cost_nok=301, status="active",
                          matched_product_id=_product("151 Booster Bundle"))
        s.add(listing)
        s.flush()
        s.add(DealEvaluation(listing_id=listing.id, price_nok=301, fair_value_nok=54627, fair_value_confidence=0.36,
                             discount_pct=0.995, total_score=40, recommendation="IGNORE", alert_level="IGNORE"))
        lid = listing.id
    items = client.get(f"{P}/market").json()["strongest_discounts"]
    assert lid not in [d["listing_id"] for d in items]
    assert all(d["confidence"] >= 0.5 for d in items)

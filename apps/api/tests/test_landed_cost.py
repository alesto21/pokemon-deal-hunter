"""Seller regions and landed cost: landed = item + shipping + import buffer (by seller region)."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from app.collectors.base import RawListing, upsert_listing
from app.collectors.cardtrader import CardTraderCollector
from app.collectors.cardtrader_mock import MockCardTraderClient
from app.db.models import Card, Listing
from app.pricing.fx import FxRates
from app.pricing.landed_cost import estimate_landed_cost, region_allowed_for_deals, region_for
from app.scoring.engine import score_listing
from app.scoring.policy import AlertState, decide

from .factories import make_ctx

NOW = datetime(2026, 10, 1, 12, 0)
FX = FxRates({"EUR": 10.0})


def test_eea_listing_has_regional_shipping_and_no_import_buffer(cfg):
    lc = estimate_landed_cost(1000, "IT", cfg.sources)
    assert (lc.seller_region, lc.shipping_nok, lc.import_buffer_nok, lc.landed_cost_nok) == ("EEA", 80, 0, 1080)
    assert region_allowed_for_deals(lc.seller_region, cfg.sources)
    assert region_for("no", cfg.sources) == "EEA"  # Norway is EEA (and survives YAML parsing)


def test_uk_listing_gets_shipping_and_import_buffer(cfg):
    lc = estimate_landed_cost(1000, "GB", cfg.sources)
    assert lc.seller_region == "UK"
    assert lc.shipping_nok == 140
    assert lc.import_buffer_nok == pytest.approx(1000 * 0.25 + 100)
    assert lc.landed_cost_nok == pytest.approx(1490)
    assert not region_allowed_for_deals("UK", cfg.sources)


def test_us_listing(cfg):
    lc = estimate_landed_cost(800, "US", cfg.sources)
    assert (lc.seller_region, lc.shipping_nok) == ("US", 250)
    assert lc.landed_cost_nok == pytest.approx(800 + 250 + 800 * 0.25 + 100)


@pytest.mark.parametrize("country", [None, "", "JP", "zz"])
def test_unknown_seller_country_is_other(cfg, country):
    lc = estimate_landed_cost(500, country, cfg.sources)
    assert lc.seller_region == "other"
    assert lc.shipping_nok == 300 and lc.import_buffer_nok == pytest.approx(500 * 0.25 + 100)
    assert not region_allowed_for_deals(lc.seller_region, cfg.sources)


def test_explicit_shipping_overrides_regional_estimate(cfg):
    assert estimate_landed_cost(500, "NO", cfg.sources, shipping_nok=69).landed_cost_nok == 569


def test_config_is_editable(cfg):
    cfg.sources.deal_seller_regions = ["EEA", "UK"]
    assert region_allowed_for_deals("UK", cfg.sources)
    cfg.sources.shipping_nok_by_region["EEA"] = 50
    assert estimate_landed_cost(100, "DE", cfg.sources).shipping_nok == 50


def test_landed_cost_discount_calculation(cfg):
    # fair value 910; EEA item 700 + 80 shipping = 780 → 14.3% discount (sticker would be 23%)
    lc = estimate_landed_cost(700, "IT", cfg.sources)
    r = score_listing(make_ctx("obvious_steal", total_price_nok=lc.landed_cost_nok), cfg)
    assert r.discount_pct == pytest.approx((910 - 780) / 910, abs=1e-4)
    # same item from the US: landed 700 + 250 + 275 = 1225 → above fair value
    us = estimate_landed_cost(700, "US", cfg.sources)
    r_us = score_listing(make_ctx("obvious_steal", total_price_nok=us.landed_cost_nok), cfg)
    assert r_us.discount_pct < 0 and r_us.total_score < r.total_score


def test_outside_region_deal_is_blocked(cfg):
    ctx = make_ctx("obvious_steal", seller_country="US", seller_region="US")
    d = decide(ctx, score_listing(ctx, cfg), AlertState(now=NOW), cfg)
    assert not d.notify
    assert any(b.startswith("seller_region_not_allowed") for b in d.blocked_by)
    eea = make_ctx("obvious_steal", seller_country="BE", seller_region="EEA")
    assert decide(eea, score_listing(eea, cfg), AlertState(now=NOW), cfg).notify


def test_fair_value_still_includes_outside_region_listings(cfg):
    def product(pid, eur, cc):
        return {"id": pid, "blueprint_id": 1, "price": {"cents": eur * 100, "currency": "EUR"},
                "properties_hash": {"condition": "Near Mint", "pokemon_language": "en"},
                "user": {"id": pid, "username": f"s{pid}", "country_code": cc}, "graded": False}

    rows = [product(1, 100, "IT"), product(2, 101, "US"), product(3, 102, "CA"), product(4, 103, "GB"),
            product(5, 104, "JP"), product(6, 105, None)]
    collector = CardTraderCollector(client=MockCardTraderClient(), cfg=cfg)
    verdicts, stats = collector.market_stats(rows, FX)
    assert all(v.included for v in verdicts)
    assert stats.count == 6  # every region counts toward fair value
    assert stats.cheapest5_median == pytest.approx(1020)  # 102 EUR x 10, item prices only (no shipping)


def test_upsert_stores_region_and_landed_cost(session, cfg):
    card = Card(name="Gastly", pokemon_name="Gastly", set_code="TEF", card_number="177/162", source_ids={})
    session.add(card)
    session.flush()
    for ext, cc in (("a", "FI"), ("b", "US"), ("c", None)):
        upsert_listing(session, RawListing(source="cardtrader", external_id=ext, title="Gastly 177/162",
                                           asking_price=80, currency="EUR", seller_country=cc, via_hub=False,
                                           known_entity=("card", card.id)), FX)
    rows = {x.external_id: x for x in session.scalars(select(Listing)).all()}
    a = rows["a"]  # direct EEA seller: estimated shipping 170 + estimated fees 20 + 1 %
    assert (a.seller_region, a.purchase_route, a.shipping_price_nok, a.fees_nok, a.import_buffer_nok) == \
        ("EEA", "direct", 170, 28, 0)
    assert a.landed_cost_nok == 800 + 170 + 28 and a.shipping_basis == "estimated" and a.fees_basis == "estimated"
    assert a.landed_cost_confidence == 0.6
    assert rows["b"].seller_region == "US" and rows["b"].landed_cost_nok == pytest.approx(800 + 250 + 28 + 300)
    assert rows["c"].seller_region == "other" and rows["c"].seller_country is None


def test_suspicious_guard_uses_item_price_not_landed_cost(cfg):
    """Shipping must not hide a too-good-to-be-true listing (live case: Mew ex at 13 EUR)."""
    ctx = make_ctx("obvious_steal", listing_price_nok=144, shipping_nok=80, total_price_nok=224, fair_value=381,
                   seller_country="BE", seller_region="EEA")
    r = score_listing(ctx, cfg)
    assert r.discount_pct < cfg.alerts.suspicious_discount <= r.item_discount_pct  # 41% landed, 62% item
    assert any("verify listing" in w for w in r.warnings)
    r.recommendation, r.total_score = "STEAL", 96
    assert decide(ctx, r, AlertState(now=NOW), cfg).severity == "STRONG_BUY"

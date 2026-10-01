"""Cheap item != cheap delivered: CardTrader delivered cost, shipping basis and seller baskets.

Live case (2026-10-01, Mew ex 205/165, direct seller): $15.90 item + $16.42 shipping + $2.02 fees
= $34.34 checkout. The old flat 80 NOK shipping made it look like a 41 % STRONG BUY.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.collectors.base import RawListing, upsert_listing
from app.collectors.cardtrader_filters import classify_listings
from app.core.config import CardTraderSourceConfig
from app.db.models import Card, Listing, SellerShippingQuote
from app.pricing.fx import FxRates
from app.pricing.landed_cost import ShippingQuote, basket_landed_cost, cardtrader_landed_cost
from app.pricing.stats import compute_stats
from app.scoring.engine import score_listing
from app.scoring.policy import AlertState, decide, effective_level

from .factories import make_ctx

USD_NOK = 9.58
MEW_ITEM, MEW_SHIP, MEW_FEES = 15.90 * USD_NOK, 16.42 * USD_NOK, 2.02 * USD_NOK  # 152, 157, 19 NOK
MEW_FV = 381.0
FX = FxRates({"EUR": 10.9, "USD": USD_NOK})


def mew_ctx(landed: float, basis: str, **kw):
    """As ingestion would build it: estimated shipping comes with estimated fees and 0.6 confidence."""
    kw.setdefault("fees_basis", basis)
    kw.setdefault("landed_cost_confidence", 1.0 if basis == "exact" else 0.6)
    return make_ctx("obvious_steal", entity_name="Mew ex", pokemon_name="Mew", card_number="205/165", set_code="MEW",
                    set_name="151", rarity="Hyper Rare", fair_value=MEW_FV, listing_price_nok=MEW_ITEM,
                    total_price_nok=landed, shipping_basis=basis, seller_country="BE", seller_region="EEA",
                    source="cardtrader", **kw)


def test_cheap_item_with_expensive_shipping_is_not_a_strong_buy(cfg):
    landed = MEW_ITEM + MEW_SHIP + MEW_FEES  # the real checkout total (~329 NOK)
    ctx = mew_ctx(landed, "exact")
    r = score_listing(ctx, cfg)
    assert r.discount_pct == pytest.approx((MEW_FV - landed) / MEW_FV, abs=1e-3)  # ~14 %, not 41 %
    assert effective_level(r, cfg).level in ("WATCH", "GOOD")
    assert decide(ctx, r, AlertState(), cfg).severity not in ("STRONG_BUY", "STEAL")


def test_estimated_cardtrader_shipping_makes_the_mew_a_non_deal(cfg):
    cost = cardtrader_landed_cost(MEW_ITEM, "BE", False, cfg.sources)  # no observed quote
    assert cost.route == "direct" and cost.shipping_basis == "estimated" and cost.fees_basis == "estimated"
    assert cost.landed_cost_nok >= MEW_ITEM + MEW_SHIP  # conservative: never below the real shipping
    r = score_listing(mew_ctx(cost.landed_cost_nok, "estimated"), cfg)
    assert r.discount_pct < cfg.alerts.minimum_discount_good  # → no alert
    assert any("verify at checkout" in w for w in r.warnings)


def test_uncertain_shipping_cannot_create_a_high_confidence_strong_buy(cfg):
    landed = MEW_FV * (1 - 0.24)  # 24 % landed discount: STRONG_BUY territory (22 %)
    est, exact = mew_ctx(landed, "estimated"), mew_ctx(landed, "exact")
    for ctx in (est, exact):
        r = score_listing(ctx, cfg)
        r.recommendation, r.total_score = "STRONG_BUY", 88
        ctx.score_result = r
    r_est, r_exact = est.score_result, exact.score_result
    lv_est, lv_exact = effective_level(r_est, cfg), effective_level(r_exact, cfg)
    assert lv_exact.level == "STRONG_BUY"
    assert lv_est.level == "GOOD"  # needs 27 % with estimated shipping
    assert any("shipping estimated" in c and "verify at checkout" in c for c in lv_est.caps)
    assert r_est.landed_cost_confidence < r_exact.landed_cost_confidence


def test_exact_shipping_quote_produces_the_checkout_total(cfg):
    q = ShippingQuote(shipment_nok=MEW_SHIP, fees_nok=MEW_FEES, capacity_items=43)
    cost = cardtrader_landed_cost(MEW_ITEM, "BE", False, cfg.sources, q)
    assert cost.shipping_basis == "exact" and cost.fees_basis == "exact" and cost.confidence == 1.0
    assert cost.landed_cost_nok == pytest.approx(34.34 * USD_NOK, abs=0.05)


def test_cardtrader_zero_route_carries_the_final_shipment_for_a_single_card(cfg):
    cost = cardtrader_landed_cost(34.94 * USD_NOK, "US", True, cfg.sources)
    assert cost.route == "zero" and cost.shipping_nok == cfg.sources.cardtrader_costs.zero_shipment_nok


@pytest.mark.parametrize("n", [2, 5, 10])
def test_seller_basket_amortises_shipping(cfg, n):
    b = basket_landed_cost([MEW_ITEM] * n, MEW_SHIP, cfg.sources, "BE", capacity_items=43)
    assert b.shipping_per_card_nok == pytest.approx(MEW_SHIP / n, abs=0.01)
    assert b.total_nok == pytest.approx(n * MEW_ITEM + MEW_SHIP + b.fees_nok, abs=0.05)
    single = cardtrader_landed_cost(MEW_ITEM, "BE", False, cfg.sources,
                                    ShippingQuote(MEW_SHIP, None, 43)).landed_cost_nok
    assert b.landed_per_card_nok[0] < single and not b.over_capacity
    assert sum(b.landed_per_card_nok) == pytest.approx(b.total_nok, abs=0.1)


def test_basket_over_seller_capacity_is_flagged(cfg):
    assert basket_landed_cost([10.0] * 50, 100, cfg.sources, "BE", capacity_items=43).over_capacity


def test_cheap_direct_listing_remains_valid_market_data():
    """The $15.90 listing is real and buyable: the problem is delivered cost, not authenticity."""
    def row(pid, usd, seller):
        return {"id": pid, "price": {"cents": int(usd * 100), "currency": "USD"}, "graded": False,
                "properties_hash": {"condition": "Near Mint", "pokemon_language": "en"},
                "user": {"id": seller, "username": f"s{seller}", "can_sell_via_hub": seller != 1}}

    rows = [row(1, 15.90, 1)] + [row(10 + i, 34.94 + i * 0.3, 10 + i) for i in range(8)]
    v = classify_listings(rows, CardTraderSourceConfig())
    assert v[0].product["id"] == 1 and v[0].included  # kept, not discarded
    assert compute_stats([x.price_cents / 100 for x in v if x.included]).low == pytest.approx(15.90)


def test_shipping_estimate_is_labelled_estimated_and_quotes_make_it_exact(session, cfg):
    card = Card(name="Mew ex", pokemon_name="Mew", set_code="MEW", card_number="205/165", source_ids={})
    session.add(card)
    session.flush()
    raw = RawListing(source="cardtrader", external_id="221687849", title="Mew ex 205", asking_price=15.90,
                     currency="USD", seller="PokeBilly", seller_external_id="4242", seller_country="BE",
                     via_hub=False, known_entity=("card", card.id))
    listing = upsert_listing(session, raw, FX)
    assert listing.shipping_basis == "estimated" and listing.landed_cost_confidence == 0.6
    assert listing.purchase_route == "direct" and listing.fees_nok > 0  # estimated fees included
    session.add(SellerShippingQuote(seller="PokeBilly", seller_external_id="4242", route="direct",
                                    shipment_nok=MEW_SHIP, fees_nok=MEW_FEES, capacity_items=43))
    session.flush()
    listing = upsert_listing(session, raw, FX)
    assert (listing.shipping_basis, listing.fees_basis) == ("exact", "exact")
    assert listing.fees_nok == pytest.approx(MEW_FEES, abs=0.01)  # known fees included
    assert listing.landed_cost_nok == pytest.approx(34.34 * USD_NOK, abs=0.05)
    assert session.scalars(select(Listing)).one().landed_cost_confidence == 1.0


def test_telegram_labels_estimated_shipping(cfg):
    from app.notifications.formatting import format_deal_alert

    ctx = mew_ctx(380, "estimated", shipping_nok=170, fees_nok=21, purchase_route="direct")
    text = format_deal_alert(ctx, score_listing(ctx, cfg), "GOOD", "CardTrader")
    assert "Shipping: 170 NOK (ESTIMATE — verify at checkout)" in text and "Fees: 21 NOK (est.)" in text
    assert "direct seller shipment" in text

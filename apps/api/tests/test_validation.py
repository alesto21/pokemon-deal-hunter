"""Market-data input: absurd asks, low-outlier logic and the final live validation gate."""

from __future__ import annotations

import copy

import pytest
from sqlalchemy import select

from app.collectors import cardtrader as ct_module
from app.collectors.cardtrader_filters import classify_listings, lower_market_base
from app.collectors.cardtrader_mock import MockCardTraderClient
from app.core.config import CardTraderSourceConfig
from app.core.http import RateLimiter
from app.db.models import Card, DealEvaluation, Listing, MarketDataConflict
from app.db.session import session_scope
from app.pricing.stats import compute_stats
from app.services import scan, validation
from app.services.evaluation import evaluate_listing

CFG = CardTraderSourceConfig()
GASTLY_BP = 900001          # mock blueprint with a planted cheap listing
CANDIDATE = "90000199"      # that cheap listing's id


def listing(pid, eur, seller=None, **props):
    p = {"condition": "Near Mint", "pokemon_language": "en"}
    p.update(props)
    return {"id": pid, "price": {"cents": round(eur * 100), "currency": "EUR"}, "properties_hash": p,
            "user": {"id": seller or pid, "username": f"s{seller or pid}"}, "graded": False, "description": ""}


# ---------------------------------------------------------------- absurd asks
def test_absurd_placeholder_asks_are_excluded_relative_to_the_lower_market():
    rows = [listing(i, 34 + i * 0.3) for i in range(1, 9)] + [listing(90, 10000.64), listing(91, 10000.64)]
    v = classify_listings(rows, CFG)
    absurd = [x for x in v if x.reason and x.reason.startswith("absurd ask")]
    assert {x.product["id"] for x in absurd} == {90, 91}
    stats = compute_stats([x.price_cents / 100 for x in v if x.included])
    assert stats.count == 8 and stats.median < 40 and stats.trimmed_median < 40


def test_thin_market_placeholder_no_longer_sets_fair_value():
    """Live case: Paldea Friends Mini Tin with asks of 20 EUR and ~10 000 EUR."""
    v = classify_listings([listing(1, 20.24), listing(2, 10000.0)], CFG)
    assert [x.included for x in v] == [True, False]


def test_absurd_rule_is_relative_not_a_fixed_price():
    rows = [listing(i, 9000 + i * 50) for i in range(1, 7)]  # a genuinely expensive card
    assert all(x.included for x in classify_listings(rows, CFG))
    assert lower_market_base([100, 200, 300, 400, 500, 600, 1_000_000]) == 250  # median of cheapest 4


# ---------------------------------------------------------------- low outlier
def test_multiple_cheap_listings_make_a_low_listing_not_an_outlier():
    lone = compute_stats([13.19, 34.21, 34.94, 34.97, 35.27, 36.28])
    assert lone.low_is_outlier  # one cheap listing far below the cluster
    cluster = compute_stats([13.19, 15.90, 15.91, 15.93, 16.20, 34.21, 34.94, 34.97])
    assert not cluster.low_is_outlier  # several cheap listings: the cheap end IS the market
    assert cluster.cheapest5_median == pytest.approx(15.91)


# ---------------------------------------------------------------- live validation gate
class LiveClient(MockCardTraderClient):
    """The mock at validation time, with optional changes to the blueprint and/or expansion views."""

    def __init__(self, mutate_bp=None, mutate_exp=None):
        self.mutate_bp, self.mutate_exp = mutate_bp, mutate_exp

    def marketplace_products(self, expansion_id=None, blueprint_id=None, language=None):
        data = copy.deepcopy(super().marketplace_products(expansion_id, blueprint_id, language))
        if blueprint_id and self.mutate_bp:
            data[str(blueprint_id)] = self.mutate_bp(data[str(blueprint_id)])
        if expansion_id and self.mutate_exp and str(GASTLY_BP) in data:
            data[str(GASTLY_BP)] = self.mutate_exp(data[str(GASTLY_BP)])
        return data


def scale(factor, only=None):
    def f(rows):
        for r in rows:
            if only is None or only(r):
                r["price"]["cents"] = int(r["price"]["cents"] * factor)
        return rows
    return f


@pytest.fixture()
def gastly_deal(engine, monkeypatch):
    """The mock's planted cheap Gastly, with an observed checkout quote for its seller (exact,
    cheap shipping) — so it is a genuine alert candidate under the delivered-cost model."""
    from app.db.models import SellerShippingQuote

    monkeypatch.setattr(validation, "_limiter", RateLimiter(1000))
    pid = int(CANDIDATE)
    with session_scope() as s:
        s.add(SellerShippingQuote(seller=f"mock_seller_{pid % 37}", seller_external_id=str(pid % 997),
                                  route="zero" if pid % 3 == 0 else "direct", shipment_nok=60, fees_nok=20,
                                  note="test fixture"))
    scan.run_collector("cardtrader", send_alerts=False)
    with session_scope() as s:
        return s.scalar(select(Listing.id).where(Listing.external_id == CANDIDATE))


def _evaluate(listing_id, notifier, monkeypatch, mutate=None, mutate_exp=None):
    if mutate is not None or mutate_exp is not None:
        monkeypatch.setattr(ct_module, "get_cardtrader_client",
                            lambda *a, **k: LiveClient(mutate, mutate_exp))
    with session_scope() as s:
        ev, _, decision = evaluate_listing(s, s.get(Listing, listing_id), notifier=notifier)
        return decision, ev.reason_json.get("validation"), ev.id


def test_validated_candidate_alerts(gastly_deal, notifier, monkeypatch):
    decision, val, _ = _evaluate(gastly_deal, notifier, monkeypatch, mutate=lambda rows: rows)
    assert decision.notify and val["status"] == "ok"
    assert val["fresh"]["fair_value_nok"] and len(notifier.sent) == 1


def test_stale_candidate_disappears_on_final_validation(gastly_deal, notifier, monkeypatch):
    def drop(rows):
        return [r for r in rows if str(r["id"]) != CANDIDATE]

    decision, val, _ = _evaluate(gastly_deal, notifier, monkeypatch, mutate=drop)
    assert not decision.notify and val["status"] == "stale"
    assert decision.blocked_by == ["live validation stale: candidate listing no longer offered"]
    assert notifier.sent == []
    with session_scope() as s:
        assert s.scalars(select(MarketDataConflict)).all() == []  # stale ≠ conflict


@pytest.mark.parametrize("factor", [1.0, 1.13, 1.3, 0.88])
def test_uniform_currency_presentation_is_not_a_conflict(gastly_deal, notifier, monkeypatch, factor):
    """Live finding: the blueprint endpoint shows EEA sellers ~13 % dearer (USD view) than the
    expansion endpoint (EUR view). A uniform presentation markup must not block EEA deals."""
    decision, val, _ = _evaluate(gastly_deal, notifier, monkeypatch, mutate=scale(factor))
    assert decision.notify, decision.blocked_by
    assert val["status"] == "ok" and val["zone_ratios"]["EEA"] == pytest.approx(factor, abs=0.005)


def test_inconsistent_listing_price_between_endpoints_is_a_conflict(gastly_deal, notifier, monkeypatch):
    """Like the live PunkOuter row (43.03 EUR vs $34.21): one listing off its region's ratio."""
    decision, val, _ = _evaluate(gastly_deal, notifier, monkeypatch,
                                 mutate=scale(1.3, only=lambda r: str(r["id"]) == CANDIDATE))
    assert not decision.notify and val["status"] == "conflict"
    assert decision.blocked_by[0].startswith("market_data_conflict:") and "inconsistent" in val["reason"]
    assert val["inconsistent_listings"][0]["id"] == CANDIDATE
    with session_scope() as s:
        c = s.scalars(select(MarketDataConflict)).one()
        assert c.source == "validation" and c.details["cheapest_rows"]["blueprint"]  # diagnostics kept
        assert c.details["scan"]["fair_value_nok"] and c.details["fresh"]["cheapest5"]
    assert notifier.sent == []


def test_expansion_data_disagrees_with_blueprint_validation(gastly_deal, notifier, monkeypatch):
    """The exact blueprint shows cheap valid offers the expansion data does not have (the Mew case)."""
    def add_cheap_offers(rows):
        template = next(r for r in rows if str(r["id"]) != CANDIDATE
                        and r["properties_hash"].get("condition") == "Near Mint"
                        and r["properties_hash"].get("pokemon_language") == "en")
        extra = []
        for i in range(3):
            r = copy.deepcopy(template)
            r["id"], r["price"]["cents"] = 777000 + i, 2000 + i
            r["user"] = {"id": 5000 + i, "username": f"cheap{i}", "country_code": "DE"}
            extra.append(r)
        return extra + rows

    decision, val, _ = _evaluate(gastly_deal, notifier, monkeypatch, mutate=add_cheap_offers)
    assert not decision.notify and val["status"] == "conflict"
    assert "disagree on cheapest valid listings" in val["reason"] and len(val["one_sided"]) == 3
    assert notifier.sent == []


def test_fair_value_moved_since_scan_is_a_conflict(gastly_deal, notifier, monkeypatch):
    move = scale(0.6, only=lambda r: str(r["id"]) != CANDIDATE)  # market 40 % cheaper since the scan
    decision, val, _ = _evaluate(gastly_deal, notifier, monkeypatch, mutate=move, mutate_exp=move)
    assert not decision.notify and val["status"] == "conflict" and "fair value moved" in val["reason"]


def test_validation_failure_never_alerts(gastly_deal, notifier, monkeypatch):
    def boom(rows):
        raise RuntimeError("API down")

    decision, val, _ = _evaluate(gastly_deal, notifier, monkeypatch, mutate=boom)
    assert not decision.notify and val["status"] == "error" and notifier.sent == []


def test_market_data_conflict_blocks_alert(gastly_deal, notifier, monkeypatch):
    with session_scope() as s:
        card_id = s.scalar(select(Card.id).where(Card.card_number == "177/162"))
        s.add(MarketDataConflict(entity_type="card", entity_id=card_id, source="manual",
                                 reason="website shows NM EN offers the API does not"))
    decision, val, ev_id = _evaluate(gastly_deal, notifier, monkeypatch)
    assert not decision.notify and val is None  # blocked before any validation request
    assert decision.blocked_by == ["market_data_conflict: website shows NM EN offers the API does not (manual)"]
    with session_scope() as s:
        assert "market_data_conflict" in s.get(DealEvaluation, ev_id).reason_json["notification"]["blocked_by"][0]
    assert notifier.sent == []

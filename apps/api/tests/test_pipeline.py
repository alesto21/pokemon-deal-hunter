"""End-to-end: mock CardTrader → snapshots → evaluation → alert policy → (fake) Telegram."""

from __future__ import annotations

from sqlalchemy import select

from app.collectors.finn import ingest_url
from app.db.models import Alert, Card, CollectorRun, DealEvaluation, Listing, PriceSnapshot, SourceStatus
from app.db.session import session_scope
from app.notifications.formatting import format_deal_alert
from app.scoring.engine import score_listing
from app.services import scan
from app.services.evaluation import evaluate_listing

from .factories import make_ctx


def test_mock_cardtrader_scan_end_to_end(engine, notifier):
    out = scan.run_collector("cardtrader", send_alerts=True, notifier=notifier)
    assert out["ok"], out
    with session_scope() as s:
        assert s.scalar(select(Card).where(Card.name == "Gastly", Card.card_number == "177/162"))
        assert s.scalars(select(PriceSnapshot)).first() is not None
        assert s.scalars(select(DealEvaluation)).first() is not None
        run = s.scalars(select(CollectorRun)).one()
        assert run.success and run.items_fetched > 0
        # cheap bulk (Gastly common) is priced but never evaluated
        bulk = s.scalar(select(Card).where(Card.card_number == "062/162"))
        assert not s.scalars(select(Listing).where(Listing.matched_card_id == bulk.id)).all()
    # second run: no duplicate alerts for the same listings
    sent_first = len(notifier.sent)
    scan.run_collector("cardtrader", send_alerts=True, notifier=notifier)
    assert len(notifier.sent) == sent_first


def test_finn_listing_evaluated_against_cardtrader_prices(engine, notifier):
    scan.run_collector("cardtrader", send_alerts=False)
    with session_scope() as s:
        listing = ingest_url(s, "https://www.finn.no/recommerce/forsale/item/412345678",
                             title="Gastly 177/162 Temporal Forces SIR NM", price=450, shipping_nok=69, fetch=False)
        assert listing.match_status == "auto"
        ev, result, decision = evaluate_listing(s, listing, notifier=notifier)
        assert ev.fair_value_nok and ev.discount_pct > 0.3
        assert decision is not None and decision.notify, decision.blocked_by
    assert notifier.sent and "Gastly" in notifier.sent[-1][0]
    assert notifier.sent[-1][1].startswith("https://www.finn.no/")


def test_health_alert_sent_once_then_recovery(engine, notifier, monkeypatch):
    class Boom:
        name = "cardtrader"

        def collect(self, session):
            raise RuntimeError("API down Bearer secret-token-123456")

    monkeypatch.setattr(scan, "collector_factories", lambda: {"cardtrader": Boom})
    for _ in range(5):
        out = scan.run_collector("cardtrader", notifier=notifier)
        assert not out["ok"] and "secret-token" not in out["error"]
    health = [m for m, _ in notifier.sent if "unhealthy" in m]
    assert len(health) == 1
    with session_scope() as s:
        st = s.get(SourceStatus, "cardtrader")
        assert st.consecutive_failures == 5 and st.health_alert_sent
        assert s.scalar(select(Alert).where(Alert.kind == "health"))

    from app.collectors.cardtrader import CardTraderCollector

    monkeypatch.setattr(scan, "collector_factories", lambda: {"cardtrader": CardTraderCollector})
    assert scan.run_collector("cardtrader", send_alerts=False, notifier=notifier)["ok"]
    assert any("recovered" in m for m, _ in notifier.sent)


def test_alert_message_format(cfg):
    ctx = make_ctx("obvious_steal", listing_price_nok=451, shipping_nok=69, total_price_nok=520,
                   title="<b>Gastly</b>", seller_country="NO", seller_region="EEA")
    r = score_listing(ctx, cfg)
    text = format_deal_alert(ctx, r, "STEAL", "FINN")
    assert text.startswith("🚨 <b>STEAL")
    assert "Source: FINN (NO, EEA)" in text and "Shipping (est.): 69 NOK" in text
    assert "Landed cost: 520 NOK" in text and "Import buffer" not in text
    uk = make_ctx("obvious_steal", listing_price_nok=300, shipping_nok=140, import_buffer_nok=175,
                  total_price_nok=615, seller_country="GB", seller_region="UK")
    assert "Import buffer (est.): 175 NOK" in format_deal_alert(uk, score_listing(uk, cfg), "GOOD", "CardTrader")
    assert "PSA10 ref: 5 300 NOK" in text
    assert "Why:" in text


def test_purge_mock_data_moves_user_data_to_live_card(engine):
    from app.db.models import PortfolioItem, WatchlistItem
    from app.services.data_hygiene import mock_rows_present, purge_mock_data, reset_price_history

    scan.run_collector("cardtrader", send_alerts=False)  # mock data
    with session_scope() as s:
        mock_gastly = s.scalar(select(Card).where(Card.name == "Gastly", Card.card_number == "177/162"))
        s.add(WatchlistItem(entity_id=mock_gastly.id, target_type="card"))
        s.add(PortfolioItem(card_id=mock_gastly.id, acquisition_price_nok=500))
        live = Card(name="Gastly", pokemon_name="Gastly", set_code="TEF", card_number="177/162",
                    rarity="Illustration Rare", source_ids={"cardtrader": 281178})
        s.add(live)
        s.flush()
        live_id = live.id
        assert mock_rows_present(s)
        out = purge_mock_data(s)
        assert out["cards_merged"] == 1 and out["snapshots_deleted"] > 0
        assert not mock_rows_present(s)
        assert s.scalars(select(WatchlistItem)).one().entity_id == live_id
        assert s.scalars(select(PortfolioItem)).one().card_id == live_id
        assert not s.scalars(select(Listing).where(Listing.source == "cardtrader")).all()
        assert reset_price_history(s)["snapshots_deleted"] == 0


def test_dry_run_alerts_do_not_suppress_live_alerts(engine, notifier):
    from app.notifications.telegram import SendResult

    class DryRun:
        dry_run = True

        def send(self, text, button_url=None, button_text=""):
            return SendResult(True, None, True)

    scan.run_collector("cardtrader", send_alerts=False)
    with session_scope() as s:
        listing = ingest_url(s, "https://www.finn.no/recommerce/forsale/item/412345670",
                             title="Gastly 177/162 Temporal Forces NM", price=450, fetch=False)
        _, _, d1 = evaluate_listing(s, listing, notifier=DryRun())
        assert d1.notify
        _, _, d2 = evaluate_listing(s, listing, notifier=DryRun())
        assert not d2.notify  # dry-run cooldown still applies within dry-run mode
        _, _, d3 = evaluate_listing(s, listing, notifier=notifier)  # live mode
        assert d3.notify, d3.blocked_by


def test_old_model_evaluations_are_refreshed(engine):
    from app.services.evaluation import needs_evaluation

    scan.run_collector("cardtrader", send_alerts=False)
    with session_scope() as s:
        ev = s.scalars(select(DealEvaluation)).first()
        listing = s.get(Listing, ev.listing_id)
        assert not needs_evaluation(s, listing)
        ev.reason_json = {**ev.reason_json, "fv_model": "old"}
        s.flush()
        assert needs_evaluation(s, listing)


def test_notification_decision_is_persisted(engine, notifier):
    scan.run_collector("cardtrader", send_alerts=False)
    with session_scope() as s:
        listing = ingest_url(s, "https://www.finn.no/recommerce/forsale/item/412345671",
                             title="Gastly 177/162 Temporal Forces NM", price=450, fetch=False)
        evaluate_listing(s, listing, notifier=notifier)
        lid = listing.id
    with session_scope() as s:  # fresh session: read back from the database
        ev = s.scalars(select(DealEvaluation).where(DealEvaluation.listing_id == lid)).one()
        assert ev.reason_json["notification"]["notify"] is True


def test_outside_region_listing_scored_but_not_alerted_end_to_end(engine, notifier):
    from app.collectors.base import RawListing, upsert_listing
    from app.pricing.fx import get_rates

    scan.run_collector("cardtrader", send_alerts=False)
    with session_scope() as s:
        card = s.scalar(select(Card).where(Card.name == "Gastly", Card.card_number == "177/162"))
        listing = upsert_listing(s, RawListing(source="cardtrader", external_id="us-1", title="Gastly 177/162",
                                               asking_price=20, currency="EUR", seller_country="US",
                                               known_entity=("card", card.id)), get_rates(s))
        ev, _, decision = evaluate_listing(s, listing, notifier=notifier)
        assert ev.price_nok == listing.landed_cost_nok > listing.total_price_nok  # import buffer included
        assert not decision.notify
        assert any(b.startswith("seller_region_not_allowed") for b in decision.blocked_by)
        lid = listing.id
    with session_scope() as s:
        ev = s.scalars(select(DealEvaluation).where(DealEvaluation.listing_id == lid)).one()
        assert ev.reason_json["landed_cost"]["seller_region"] == "US"
        assert any("seller_region_not_allowed" in b for b in ev.reason_json["notification"]["blocked_by"])
    assert not notifier.sent

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
                   title="<b>Gastly</b>")
    r = score_listing(ctx, cfg)
    text = format_deal_alert(ctx, r, "STEAL", "FINN")
    assert text.startswith("🚨 <b>STEAL")
    assert "Source: FINN" in text and "Shipping: 69 NOK" in text and "Total: 520 NOK" in text
    assert "PSA10 ref: 5 300 NOK" in text
    assert "Why:" in text

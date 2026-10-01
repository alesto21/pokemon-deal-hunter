"""FINN ingestion (user-driven: capture / URL / CSV), lot detection, economics, safety labels.

FINN's robots.txt prohibits automated crawling without written permission, so there is no search
scraper. These tests never touch the network (any HTTP call fails the test)."""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from typer.testing import CliRunner

from app.api.main import create_app
from app.collectors.finn_text import extract_lot_details, parse_shipping
from app.db.base import utcnow
from app.db.models import Alert, Listing, Lot
from app.db.session import session_scope
from app.services import scan

URL = "https://www.finn.no/recommerce/forsale/item/{}"


@pytest.fixture(autouse=True)
def no_finn_requests(monkeypatch):
    """Any request to a FINN host fails the test (the in-process TestClient is allowed)."""
    real_send = httpx.Client.send

    def guarded(self, request, *a, **k):
        if "finn.no" in (request.url.host or ""):
            raise AssertionError(f"the app must not contact FINN ({request.url})")
        return real_send(self, request, *a, **k)

    monkeypatch.setattr(httpx.Client, "send", guarded)


@pytest.fixture()
def client(engine):
    scan.run_collector("cardtrader", send_alerts=False)  # mock catalogue + market (no network)
    return TestClient(create_app())


def capture(client, code, title, price, **kw):
    r = client.post("/api/v1/finn/capture", json={"url": URL.format(code), "title": title, "price": price, **kw})
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- text analysis (pure)
@pytest.mark.parametrize("text,kind,amount", [
    ("Sendes for 79 kr", "unknown", None),            # "sendes for 79 kr" alone is ambiguous → not exact
    ("Frakt 69 kr med Posten", "exact", 69),
    ("99,- i frakt", "exact", 99),
    ("Fri frakt!", "included", 0),
    ("Frakt inkludert i prisen", "included", 0),
    ("Kun henting på Grünerløkka", "pickup", 0),
    ("Kan sendes eller hentes", "unknown", None),
])
def test_shipping_parsing(text, kind, amount):
    info = parse_shipping(text)
    assert info.kind == kind and info.amount_nok == amount


def test_capture_payload_is_validated(client):
    assert client.post("/api/v1/finn/capture", json={"url": "https://evil.example/x", "title": "x",
                                                      "price": 1}).status_code == 422
    assert client.post("/api/v1/finn/capture", json={"url": URL.format(1234567), "title": "x",
                                                      "price": -5}).status_code == 422


# ---------------------------------------------------------------- ingestion
def test_new_listing_ingestion_stores_capture_details(client):
    body = capture(client, 401000001, "Gastly 177/162 Temporal Forces SIR", 450,
                   description="Gastly illustration rare, near mint. Frakt 69 kr.", location="Oslo",
                   seller="Kari", seller_type="private", image_urls=["https://images.finncdn.no/a.jpg"])
    assert body["source"] == "finn" and body["capture_method"] == "capture" and body["location"] == "Oslo"
    assert body["match_status"] == "auto" and body["entity_label"].startswith("Gastly")  # single-card match
    assert (body["shipping_price_nok"], body["shipping_basis"]) == (69, "exact")
    assert body["landed_cost_nok"] == 519 and body["evaluation"]["fair_value_nok"]


def test_duplicate_finn_listing_is_updated_not_duplicated_and_price_change_kept(client):
    capture(client, 401000002, "Gastly 177/162 Temporal Forces", 600, description="Frakt 69 kr, fin stand")
    capture(client, 401000002, "Gastly 177/162 Temporal Forces", 520, description="Frakt 69 kr, fin stand")
    with session_scope() as s:
        rows = s.scalars(select(Listing).where(Listing.external_id == "401000002")).all()
        assert len(rows) == 1
        assert rows[0].total_price_nok == 589 and rows[0].previous_total_price_nok == 669  # changed price


def test_duplicate_looking_listing_is_labelled(client):
    capture(client, 401000003, "Pikachu 173/165 151 til salgs", 300, description="kort tekst")
    other = capture(client, 401000004, "Pikachu 173/165 151 til salgs", 300, description="kort tekst")
    assert any(f.startswith("duplicate-looking") for f in other["safety_flags"])
    assert any(f.startswith("low information") for f in other["safety_flags"])


def test_removed_listing_is_marked_gone(client):
    from app.services.maintenance import run_maintenance

    body = capture(client, 401000005, "Raichu 211/193 Paldea Evolved", 150, description="Frakt 69 kr. " * 5)
    with session_scope() as s:
        s.get(Listing, body["id"]).last_seen = utcnow() - timedelta(days=30)
    run_maintenance()
    with session_scope() as s:
        assert s.get(Listing, body["id"]).status == "gone"


def test_sealed_match(client):
    body = capture(client, 401000006, "Paradox Rift booster box forseglet", 1700,
                   description="Uåpnet display med 36 pakker. Kun henting i Bergen.")
    assert body["listing_kind"] == "sealed" and body["matched_product_id"]
    assert body["pickup_required"] is True and body["shipping_basis"] == "pickup"
    assert any("pickup required" in w for w in body["evaluation"]["warnings"])


def test_ambiguous_listing_goes_to_review_without_identity(client):
    body = capture(client, 401000007, "Gastly kort fint", 200, description="Pent brukt Gastly kort, sendes.")
    assert body["match_status"] == "unresolved" and body["matched_card_id"] is None  # queued for review
    review_ids = [x["id"] for x in client.get("/api/v1/review").json()]
    assert body["id"] in review_ids


def test_unknown_shipping_is_estimated_and_labelled(client):
    body = capture(client, 401000008, "Pikachu 173/165 151", 250, description="Kan sendes, ta kontakt")
    assert body["shipping_basis"] == "estimated" and body["shipping_price_nok"] == 99
    assert body["landed_cost_confidence"] == 0.6
    assert "shipping estimate — verify at checkout" in body["evaluation"]["warnings"]


def test_user_entered_shipping_is_exact(client):
    body = capture(client, 401000009, "Pikachu 173/165 151", 250, shipping_nok=45, description="x" * 50)
    assert (body["shipping_basis"], body["shipping_price_nok"], body["landed_cost_confidence"]) == ("exact", 45, 1.0)


# ---------------------------------------------------------------- lots
def test_lot_detection_extraction_and_partial_value(client):
    desc = ("Selger samlingen min, ca 200 kort. Inneholder bl.a. Gastly 177/162 og Charizard ex 199/165, "
            "pluss noen PSA 9 og PSA 10 kort og en 151 Elite Trainer Box. Resten er bulk. Kun henting.")
    body = capture(client, 401000010, "Pokemon samling 200 kort", 1500, description=desc)
    assert body["listing_kind"] == "lot" and body["matched_card_id"] is None  # never forced to one card
    lot = body["extracted"]["lot"]
    assert lot["is_lot"] and lot["stated_quantity"] == 200
    assert set(lot["card_numbers"]) >= {"177/162", "199/165"} and "PSA 10" in lot["grades"]
    with session_scope() as s:
        lot_row = s.scalar(select(Lot).where(Lot.listing_id == body["id"]))
        assert lot_row.stated_quantity == 200
        assert {i.origin for i in lot_row.items} == {"auto"}
        identified = lot_row.extraction["identified"]
        assert any(x.startswith("Gastly") for x in identified) and any(x.startswith("Charizard") for x in identified)
    ev = body["evaluation"]
    assert ev["details"]["lot"]["coverage"] < 0.1  # 2-3 of 200 items identified
    # never alerts: either the identified part is worth less than the price, or — even when it is
    # worth more — 2-3 of 200 items is far below the coverage required to trust a lot valuation
    assert ev["notification"]["notify"] is False
    blocked = ev["notification"]["blocked_by"]
    # stopped by the low score (fair-value confidence ≈ coverage) or by the coverage gate itself
    assert any(b.startswith("lot: only") or "IGNORE" in b or "WATCH" in b for b in blocked), blocked
    assert ev["fair_value_confidence"] < 0.1 and "lot_partial_value" in ev["details"]["fair_value_flags"]


def test_number_without_named_pokemon_is_not_identified(client):
    body = capture(client, 401000011, "Kortsamling selges", 800,
                   description="Ca 50 kort i perm. Har bl.a. 177/162 og 199/165. Sendes.")
    with session_scope() as s:
        lot_row = s.scalar(select(Lot).where(Lot.listing_id == body["id"]))
        assert lot_row.items == []  # numbers alone are not enough: no Pokémon named
        assert sorted(lot_row.extraction["unrecognised_numbers"]) == ["177/162", "199/165"]


def test_lot_alert_requires_coverage(client, cfg, notifier):
    from app.scoring.engine import score_listing
    from app.scoring.policy import AlertState, decide

    from .factories import make_ctx

    for coverage, unknown, expect in ((None, True, "unknown"), (0.4, False, "only 40%"), (0.9, False, None)):
        ctx = make_ctx("obvious_steal", listing_kind="lot", lot_coverage=coverage,
                       lot_unidentified=None if unknown else 3)
        d = decide(ctx, score_listing(ctx, cfg), AlertState(), cfg)
        lot_blocks = [b for b in d.blocked_by if b.startswith("lot:")]
        if expect is None:
            assert lot_blocks == []
        else:
            assert lot_blocks and expect in lot_blocks[0]


def test_single_card_text_is_not_a_lot():
    from app.core.config import load_user_config

    d = extract_lot_details("Charizard ex 199/165 SIR", "Strøken, sendes i toploader", load_user_config().sets,
                            ["Charizard"])
    assert not d.is_lot


# ---------------------------------------------------------------- alerts & discovery
def test_no_duplicate_alerts_for_recaptured_listing(client, monkeypatch):
    from app.notifications import telegram

    class Live(telegram.TelegramNotifier):
        def __init__(self):
            self.dry_run, self.sent = False, []

        def send(self, text, button_url=None, button_text=""):
            self.sent.append(text)
            return telegram.SendResult(True, len(self.sent), False)

    notifier = Live()
    monkeypatch.setattr("app.services.evaluation.TelegramNotifier", lambda: notifier)
    for _ in range(3):
        capture(client, 401000012, "Gastly 177/162 Temporal Forces", 380, shipping_nok=50,
                description="Gastly illustration rare i perfekt stand. Sendes rekommandert.")
    with session_scope() as s:
        assert len(s.scalars(select(Alert).where(Alert.kind == "deal")).all()) <= 1
    assert len(notifier.sent) <= 1


def test_no_automated_finn_discovery():
    from app.cli import cli
    from app.core.config import load_user_config

    assert load_user_config().sources.finn.fetch_metadata is False
    result = CliRunner().invoke(cli, ["finn-scan-now"])
    assert result.exit_code == 2 and "written consent" in result.output

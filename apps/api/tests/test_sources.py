from __future__ import annotations

import httpx
import pytest

from app.collectors import finn
from app.collectors.cardtrader import pokemon_name_from, product_type_from
from app.collectors.cardtrader_client import CardTraderClient
from app.core.logging import redact_text
from app.core.security import InvalidURLError, sanitize_text, validate_url


def test_validate_url_rules():
    assert validate_url("https://www.finn.no/recommerce/forsale/item/123456789#x", ("finn.no",)) \
        == "https://www.finn.no/recommerce/forsale/item/123456789"
    for bad in ("ftp://finn.no/x", "http://127.0.0.1/x", "http://localhost/x", "https://evil.com/x",
                "https://user:pw@finn.no/x"):
        with pytest.raises(InvalidURLError):
            validate_url(bad, ("finn.no",))


def test_sanitize_text():
    assert sanitize_text("  Gastly\x00  177/162\n\n NM ") == "Gastly 177/162 NM"
    assert len(sanitize_text("x" * 1000, 50)) == 50


def test_finn_code_extraction():
    assert finn.finn_code("https://www.finn.no/bap/forsale/ad.html?finnkode=312345678") == "312345678"
    assert finn.finn_code("https://www.finn.no/recommerce/forsale/item/412345678") == "412345678"
    with pytest.raises(finn.FinnIngestError):
        finn.finn_code("https://www.finn.no/")


def test_parse_listing_html_meta_and_jsonld():
    html = """<html><head><title>x</title>
    <meta property="og:title" content="Gastly 177/162 SIR">
    <meta property="og:image" content="https://images.finncdn.no/a.jpg">
    <script type="application/ld+json">{"@type":"Product","offers":{"price":"625","priceCurrency":"NOK"}}</script>
    </head></html>"""
    md = finn.parse_listing_html(html)
    assert md.title == "Gastly 177/162 SIR" and md.price == 625 and md.currency == "NOK"


def test_finn_ingest_requires_price_when_not_fetchable(session):
    with pytest.raises(finn.FinnIngestError):
        finn.ingest_url(session, "https://www.finn.no/recommerce/forsale/item/412345678", fetch=False)
    listing = finn.ingest_url(session, "https://www.finn.no/recommerce/forsale/item/412345678",
                              title="Gastly 177/162", price=625, shipping_nok=69, fetch=False)
    assert listing.total_price_nok == 694 and listing.source == "finn" and listing.external_id == "412345678"


def test_finn_import_parsing():
    rows = finn.parse_import("url,title,price\nhttps://www.finn.no/item/123456789,Gastly 177/162,625\n")
    assert rows[0]["price"] == 625 and rows[0]["currency"] == "NOK"


def test_cardtrader_client_uses_bearer_and_parses(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["Authorization"]
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"123": [{"id": 1, "price": {"cents": 1234, "currency": "EUR"}}]})

    c = CardTraderClient("tok", "https://api.cardtrader.com/api/v2", rate_per_second=100,
                         transport=httpx.MockTransport(handler))
    data = c.marketplace_products(expansion_id=42, language="en")
    assert seen["auth"] == "Bearer tok"
    assert seen["path"] == "/api/v2/marketplace/products"
    assert seen["params"] == {"expansion_id": "42", "language": "en"}
    assert data["123"][0]["price"]["cents"] == 1234


def test_cardtrader_client_retries_then_raises():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(503)

    c = CardTraderClient("tok", "https://x.test", rate_per_second=100, transport=httpx.MockTransport(handler))
    c.http.max_retries = 1
    import app.core.http as h

    orig = h.time.sleep
    h.time.sleep = lambda s: None
    try:
        with pytest.raises(h.SourceHTTPError):
            c.info()
    finally:
        h.time.sleep = orig
    assert calls["n"] == 2


def test_cardtrader_name_and_category_mapping():
    assert pokemon_name_from("Charizard ex") == "Charizard"
    assert pokemon_name_from("Mew VMAX") == "Mew"
    assert product_type_from("Pokemon Single Card", "Gastly") is None
    assert product_type_from("Booster Box", "Paradox Rift Booster Box") == "booster_box"
    assert product_type_from("Sealed", "151 Elite Trainer Box") == "etb"


def test_secret_redaction():
    t = redact_text("POST https://api.telegram.org/bot123456789:AAAbbbCCCdddEEEfffGGGhhhIII/sendMessage")
    assert "AAAbbb" not in t
    assert "Bearer ***REDACTED***" in redact_text("Authorization: Bearer abcdefghijklmnop")

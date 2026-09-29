from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.main import create_app
from app.core.config import get_settings


@pytest.fixture()
def client(engine):
    return TestClient(create_app())


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_api_key_enforced(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "api_key", SecretStr("k3y"))
    assert client.get("/api/v1/overview").status_code == 401
    assert client.get("/api/v1/overview", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/v1/overview", headers={"X-API-Key": "k3y"}).status_code == 200


def test_manual_listing_flow_and_review(client):
    client.post("/api/v1/sources/cardtrader/run")  # background task runs synchronously in TestClient
    r = client.post("/api/v1/listings/manual", json={
        "url": "https://www.finn.no/recommerce/forsale/item/412345678", "title": "Gastly 177/162 SIR",
        "price": 500, "shipping_nok": 69, "fetch_metadata": False})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["evaluation"]["fair_value_nok"] > 0
    deals = client.get("/api/v1/deals", params={"source": "finn"}).json()
    assert deals["total"] == 1
    bad = client.post("/api/v1/listings/manual", json={"url": "https://evil.example.com/x", "price": 1,
                                                       "title": "x", "fetch_metadata": False})
    assert bad.status_code == 422
    # ambiguous title goes to review; accept a candidate manually
    r = client.post("/api/v1/listings/manual", json={
        "url": "https://www.finn.no/recommerce/forsale/item/412345679", "title": "Gastly kort",
        "price": 300, "fetch_metadata": False})
    lid = r.json()["id"]
    assert r.json()["match_status"] in ("review", "unresolved")
    card_id = client.get("/api/v1/cards", params={"q": "177/162"}).json()[0]["id"]
    r = client.post(f"/api/v1/review/{lid}", json={"action": "set", "entity_type": "card", "entity_id": card_id})
    assert r.json()["match_status"] == "manual" and r.json()["matched_card_id"] == card_id


def test_portfolio_watchlist_and_prices(client):
    client.post("/api/v1/sources/cardtrader/run")
    card_id = client.get("/api/v1/cards", params={"q": "Charizard"}).json()[0]["id"]
    assert client.post("/api/v1/portfolio", json={"card_id": card_id, "acquisition_price_nok": 1200,
                                                  "binder_type": "premium"}).status_code == 201
    s = client.get("/api/v1/portfolio/summary").json()
    assert s["total_cost_nok"] == 1200 and s["raw_value_nok"] > 0
    assert client.post("/api/v1/watchlist", json={"entity_id": card_id, "target_buy_price": 1000}).status_code == 201
    h = client.get(f"/api/v1/prices/card/{card_id}").json()
    assert h["raw"] and h["portfolio_entries"][0]["price_nok"] == 1200
    assert client.get("/api/v1/settings").json()["modes"]["cardtrader"] == "mock"
    assert client.post("/api/v1/telegram/test").json()["dry_run"] is True
    assert {s["source"] for s in client.get("/api/v1/sources").json()} == {"cardtrader", "stores", "finn"}


def test_lot_valuation(client):
    client.post("/api/v1/sources/cardtrader/run")
    r = client.post("/api/v1/listings/manual", json={
        "url": "https://www.finn.no/recommerce/forsale/item/512345678", "title": "Pokemon samling 300 kort",
        "price": 1500, "fetch_metadata": False})
    lid = r.json()["id"]
    lot = client.post("/api/v1/lots", json={"listing_id": lid}).json()
    card_id = client.get("/api/v1/cards", params={"q": "Charizard"}).json()[0]["id"]
    client.post(f"/api/v1/lots/{lot['id']}/items", json={"card_id": card_id, "quantity": 1})
    v = client.post(f"/api/v1/lots/{lot['id']}/items", json={"label": "bulk", "manual_value_nok": 200}).json()
    assert v["valuation"]["priced_items"] == 2
    assert v["valuation"]["conservative_value_nok"] < v["valuation"]["estimated_value_nok"]
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 100
    up = client.post(f"/api/v1/lots/{lot['id']}/images", files={"file": ("a.png", png, "image/png")})
    assert up.status_code == 201
    assert client.post(f"/api/v1/lots/{lot['id']}/images",
                       files={"file": ("a.png", b"not an image", "image/png")}).status_code == 415

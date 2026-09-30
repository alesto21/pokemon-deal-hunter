from __future__ import annotations

import pytest

from app.collectors.cardtrader import parse_version
from app.collectors.cardtrader_filters import classify_listings, exclusion_reason
from app.core.config import CardTraderSourceConfig

CFG = CardTraderSourceConfig()


def listing(pid=1, cents=10000, seller=1, **props_and_fields) -> dict:
    props = {"condition": "Near Mint", "pokemon_language": "en", "pokemon_reverse": False, "signed": False,
             "altered": False, "first_edition": False}
    fields = {k: props_and_fields.pop(k) for k in ("graded", "description", "on_vacation", "bundle_size")
              if k in props_and_fields}
    props.update(props_and_fields)
    return {"id": pid, "price": {"cents": cents, "currency": "EUR"}, "properties_hash": props,
            "user": {"id": seller, "username": f"s{seller}"}, "graded": False, "description": "", **fields}


@pytest.mark.parametrize("kwargs,reason", [
    ({}, None),
    ({"pokemon_language": "it"}, "language it"),
    ({"condition": "Slightly Played"}, "condition Slightly Played"),
    ({"graded": True}, "graded (flag)"),
    ({"description": "PSA 9 MINT"}, "graded (description)"),
    ({"pokemon_reverse": True}, "reverse holo variant"),
    ({"signed": True}, "signed"),
    ({"altered": True}, "altered"),
    ({"first_edition": True}, "1st edition variant"),
    ({"description": "custom proxy art"}, "description red flag"),
    ({"description": "Japanese version"}, "description suggests non-English"),
    ({"on_vacation": True}, "seller on vacation"),
    ({"bundle_size": 4}, "bundle listing"),
    ({"description": "Holo Huge selection, no shipping on holidays"}, None),
])
def test_exclusion_reasons(kwargs, reason):
    assert exclusion_reason(listing(**kwargs), CFG) == reason


def test_sealed_products_without_condition_are_valid():
    p = listing()
    p["properties_hash"] = {"pokemon_language": "en"}
    assert exclusion_reason(p, CFG) is None


def test_one_listing_per_seller_and_sorted():
    rows = [listing(1, 9000, seller=7), listing(2, 7000, seller=7), listing(3, 8000, seller=8)]
    v = classify_listings(rows, CFG)
    assert [x.product["id"] for x in v] == [2, 3, 1]
    assert [x.included for x in v] == [True, True, False]
    assert v[2].reason == "same seller already counted"


@pytest.mark.parametrize("version,expected", [
    ("102/162", ("102/162", None)),
    ("Illustration Rare | 177/162", ("177/162", "Illustration Rare")),
    ("Full-Art 193/162", ("193/162", None)),
    ("Special Illustration Rare | 204/162", ("204/162", "Special Illustration Rare")),
    ("TG05/TG30", ("TG05/TG30", None)),
    (None, (None, None)),
])
def test_parse_version(version, expected):
    assert parse_version(version) == expected

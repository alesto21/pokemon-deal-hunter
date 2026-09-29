from __future__ import annotations

import pytest

from app.db.models import Card, MatchStatus, Product
from app.matching.matcher import match_listing, status_for
from app.matching.normalize import normalize_number, parse_title


def test_normalize_number():
    assert normalize_number("007") == "7"
    assert normalize_number("TG05") == "TG5"
    assert normalize_number("SVP 085") == "SVP85"


@pytest.mark.parametrize("title,number,total,set_code", [
    ("Gastly 177/162 Temporal Forces SIR", "177", "162", "TEF"),
    ("Pikachu 173/165 Pokémon 151 illustration rare", "173", "165", "MEW"),
    ("Tyranitar 222/193 PAL NM", "222", "193", "PAL"),
    ("Eevee 188/167", "188", "167", "TWM"),  # set inferred from printed total
])
def test_parse_title_numbers_and_sets(cfg, title, number, total, set_code):
    p = parse_title(title, cfg.sets)
    assert (p.number, p.total, p.set_code) == (number, total, set_code)


def test_parse_title_products_lots_language_grades(cfg):
    assert parse_title("Paradox Rift Booster Box 36 pakker", cfg.sets).product_type == "booster_box"
    assert parse_title("151 Elite Trainer Box ny forseglet", cfg.sets).product_type == "etb"
    assert parse_title("Pokemon samling 1500 kort", cfg.sets).is_lot
    assert parse_title("Gastly 177/162 japansk", cfg.sets).language == "ja"
    p = parse_title("Charizard ex PSA 10 199/165", cfg.sets)
    assert p.grade_company == "PSA" and p.grade == 10


def test_status_bands():
    assert status_for(0.95) == MatchStatus.AUTO
    assert status_for(0.8) == MatchStatus.REVIEW
    assert status_for(0.5) == MatchStatus.UNRESOLVED


@pytest.fixture()
def catalogue(session):
    cards = [
        Card(name="Gastly", pokemon_name="Gastly", set_code="TEF", set_name="Temporal Forces",
             card_number="177/162", rarity="Special Illustration Rare", source_ids={}),
        Card(name="Gastly", pokemon_name="Gastly", set_code="TEF", set_name="Temporal Forces",
             card_number="062/162", rarity="Common", source_ids={}),
        Card(name="Pikachu", pokemon_name="Pikachu", set_code="MEW", set_name="151",
             card_number="173/165", rarity="Illustration Rare", source_ids={}),
        Card(name="Pikachu", pokemon_name="Pikachu", set_code="MEW", set_name="151",
             card_number="025/165", rarity="Common", source_ids={}),
    ]
    prods = [Product(name="Paradox Rift Booster Box", product_type="booster_box", set_code="PAR",
                     set_name="Paradox Rift", pack_count=36, source_ids={})]
    session.add_all(cards + prods)
    session.flush()
    return cards, prods


def test_exact_card_auto_matches(session, cfg, catalogue):
    cards, _ = catalogue
    r = match_listing(session, "Gastly 177/162 Temporal Forces SIR NM", cfg.sets)
    assert r.status == MatchStatus.AUTO and r.entity_id == cards[0].id and r.confidence >= 0.9


def test_number_disambiguates_same_pokemon(session, cfg, catalogue):
    cards, _ = catalogue
    r = match_listing(session, "Pikachu 025/165 151", cfg.sets)
    assert r.entity_id == cards[3].id


def test_name_only_is_never_auto(session, cfg, catalogue):
    r = match_listing(session, "Gastly kort pent brukt", cfg.sets)
    assert r.status != MatchStatus.AUTO


def test_wrong_language_is_not_auto(session, cfg, catalogue):
    r = match_listing(session, "Gastly 177/162 Temporal Forces japansk", cfg.sets)
    assert r.status != MatchStatus.AUTO


def test_sealed_product_match(session, cfg, catalogue):
    _, prods = catalogue
    r = match_listing(session, "Paradox Rift booster box forseglet", cfg.sets)
    assert r.entity_type == "product" and r.entity_id == prods[0].id and r.status == MatchStatus.AUTO


def test_lot_is_unresolved(session, cfg, catalogue):
    assert match_listing(session, "Stor pokemon samling selges", cfg.sets).status == MatchStatus.UNRESOLVED

"""Deterministic MOCK CardTrader data for development without an API token.

Prices here are illustrative sample values, NOT real market data. The mock is
only active when CARDTRADER_API_TOKEN is empty (or CARDTRADER_MOCK=true).
"""

from __future__ import annotations

import random
import time
from typing import Any

GAME_ID = 5
CAT_SINGLE, CAT_BOX, CAT_PACK, CAT_BUNDLE, CAT_ETB = 73, 74, 75, 76, 77

EXPANSIONS = [
    {"id": 3601, "game_id": GAME_ID, "code": "tef", "name": "Temporal Forces"},
    {"id": 3402, "game_id": GAME_ID, "code": "pal", "name": "Paldea Evolved"},
    {"id": 3702, "game_id": GAME_ID, "code": "twm", "name": "Twilight Masquerade"},
    {"id": 3450, "game_id": GAME_ID, "code": "mew", "name": "151"},
    {"id": 3520, "game_id": GAME_ID, "code": "par", "name": "Paradox Rift"},
]

# (blueprint_id, expansion_id, category, name, collector_number, rarity, base_eur, n_listings, deal_factor)
_BP = [
    (900001, 3601, CAT_SINGLE, "Gastly", "177/162", "Special Illustration Rare", 78.0, 14, 0.66),
    (900002, 3601, CAT_SINGLE, "Walking Wake ex", "205/162", "Special Illustration Rare", 28.0, 20, None),
    (900003, 3601, CAT_SINGLE, "Gastly", "062/162", "Common", 0.15, 40, 0.5),
    (900004, 3601, CAT_SINGLE, "Iron Leaves ex", "203/162", "Special Illustration Rare", 24.0, 18, None),
    (900101, 3402, CAT_SINGLE, "Raichu", "211/193", "Illustration Rare", 16.0, 16, None),
    (900102, 3402, CAT_SINGLE, "Tyranitar", "222/193", "Illustration Rare", 34.0, 11, 0.8),
    (900103, 3402, CAT_SINGLE, "Magikarp", "203/193", "Illustration Rare", 62.0, 12, None),
    (900201, 3702, CAT_SINGLE, "Eevee", "188/167", "Illustration Rare", 38.0, 15, None),
    (900202, 3702, CAT_SINGLE, "Greninja ex", "214/167", "Special Illustration Rare", 58.0, 12, None),
    (900301, 3450, CAT_SINGLE, "Pikachu", "173/165", "Illustration Rare", 21.0, 25, 0.85),
    (900302, 3450, CAT_SINGLE, "Charizard ex", "199/165", "Special Illustration Rare", 118.0, 22, None),
    (900303, 3450, CAT_SINGLE, "Mew ex", "205/165", "Hyper Rare", 48.0, 9, None),
    (900401, 3520, CAT_BOX, "Paradox Rift Booster Box", None, None, 195.0, 8, None),
    (900402, 3520, CAT_PACK, "Paradox Rift Booster Pack", None, None, 5.2, 30, None),
    (900403, 3450, CAT_BUNDLE, "151 Booster Bundle", None, None, 58.0, 10, None),
    (900404, 3450, CAT_ETB, "151 Elite Trainer Box", None, None, 92.0, 7, None),
]

_CATEGORIES = [
    {"id": CAT_SINGLE, "name": "Pokemon Single Card", "game_id": GAME_ID, "properties": []},
    {"id": CAT_BOX, "name": "Booster Box", "game_id": GAME_ID, "properties": []},
    {"id": CAT_PACK, "name": "Booster Pack", "game_id": GAME_ID, "properties": []},
    {"id": CAT_BUNDLE, "name": "Booster Bundle", "game_id": GAME_ID, "properties": []},
    {"id": CAT_ETB, "name": "Elite Trainer Box", "game_id": GAME_ID, "properties": []},
]

_CONDITIONS = ["Near Mint"] * 7 + ["Mint", "Slightly Played", "Moderately Played"]
_LANGS = ["en"] * 8 + ["de", "it"]


class MockCardTraderClient:
    is_mock = True

    def info(self) -> dict[str, Any]:
        return {"id": 0, "name": "MOCK CardTrader app", "user_id": 0}

    def games(self) -> list[dict[str, Any]]:
        return [{"id": 1, "name": "Magic", "display_name": "Magic: the Gathering"},
                {"id": GAME_ID, "name": "Pokemon", "display_name": "Pokémon"}]

    def categories(self, game_id: int) -> list[dict[str, Any]]:
        return [c for c in _CATEGORIES if c["game_id"] == game_id]

    def expansions(self) -> list[dict[str, Any]]:
        return EXPANSIONS

    def blueprints(self, expansion_id: int) -> list[dict[str, Any]]:
        out = []
        for bp_id, exp_id, cat, name, num, rarity, *_ in _BP:
            if exp_id != expansion_id:
                continue
            fixed = {"collector_number": num, "pokemon_rarity": rarity} if num else {}
            out.append({"id": bp_id, "name": name, "version": None, "game_id": GAME_ID, "category_id": cat,
                        "expansion_id": exp_id, "image_url": None, "fixed_properties": fixed,
                        "editable_properties": []})
        return out

    def marketplace_products(self, expansion_id: int | None = None, blueprint_id: int | None = None,
                             language: str | None = None) -> dict[str, list[dict[str, Any]]]:
        exp = {e["id"]: e for e in EXPANSIONS}
        bucket = int(time.time() // 1800)  # prices drift a little every 30 minutes
        out: dict[str, list[dict[str, Any]]] = {}
        for bp_id, exp_id, cat, name, num, rarity, base, n, deal in _BP:
            if (expansion_id and exp_id != expansion_id) or (blueprint_id and bp_id != blueprint_id):
                continue
            rng = random.Random(bp_id * 7919 + bucket)
            drift = 1 + 0.03 * ((bucket % 48) / 48 - 0.5)
            products = []
            for i in range(n):
                price = base * drift * (1 + rng.uniform(-0.06, 0.35))
                lang = rng.choice(_LANGS)
                if language and lang != language:
                    continue
                props: dict[str, Any] = {"pokemon_language": lang}
                if cat == CAT_SINGLE:
                    props.update(condition=rng.choice(_CONDITIONS), collector_number=num, pokemon_rarity=rarity)
                products.append(self._product(bp_id * 100 + i, bp_id, name, price, props, exp[exp_id], rng))
            if deal:
                props = {"pokemon_language": "en"}
                if cat == CAT_SINGLE:
                    props.update(condition="Near Mint", collector_number=num, pokemon_rarity=rarity)
                products.append(self._product(bp_id * 100 + 99, bp_id, name, base * deal, props, exp[exp_id], rng))
            out[str(bp_id)] = products
        return out

    @staticmethod
    def _product(pid: int, bp_id: int, name: str, price_eur: float, props: dict, exp: dict,
                 rng: random.Random) -> dict[str, Any]:
        return {
            "id": pid, "blueprint_id": bp_id, "name_en": name, "quantity": rng.randint(1, 3),
            "price": {"cents": int(round(price_eur * 100)), "currency": "EUR"},
            "description": "", "properties_hash": props,
            "expansion": {"id": exp["id"], "code": exp["code"], "name_en": exp["name"]},
            "user": {"id": pid % 997, "username": f"mock_seller_{pid % 37}", "can_sell_via_hub": pid % 3 == 0,
                     "country_code": rng.choice(["IT", "DE", "FR", "NL", "SE"]), "user_type": "normal"},
            "graded": False, "on_vacation": False, "bundle_size": 1,
        }

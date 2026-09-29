"""CardTrader collector: catalogue sync, price snapshots and deal candidates.

One ``/marketplace/products?expansion_id=`` request returns the listings for
every item in a set, so a full scan costs one request per tracked set.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.base import CollectorResult, RawListing, upsert_listing
from app.collectors.cardtrader_client import CardTraderAPI, get_cardtrader_client
from app.core.config import SetMeta, UserConfig, get_user_config
from app.core.logging import get_logger
from app.db.models import Card, EntityType, Product, ProductType, WatchlistItem
from app.matching.normalize import PRODUCT_KEYWORDS, fold, split_card_number
from app.pricing.fx import FxRates, get_rates
from app.pricing.history import record_snapshot
from app.pricing.stats import compute_stats

log = get_logger(__name__)
SOURCE = "cardtrader"
_SUFFIXES = re.compile(r"\s+(ex|EX|GX|V|VMAX|VSTAR|V-UNION|BREAK|LV\.X|δ|Prime|LEGEND|☆)$")


def pokemon_name_from(card_name: str) -> str:
    name = card_name.strip()
    while True:
        new = _SUFFIXES.sub("", name)
        if new == name:
            return name
        name = new


def product_type_from(category_name: str, name: str) -> str | None:
    """Map a CardTrader category/blueprint name to our ProductType, None for singles."""
    cat = fold(category_name)
    if "single" in cat:
        return None
    text = f" {cat} {fold(name)} "
    for ptype, words in PRODUCT_KEYWORDS:
        if any(w in text for w in words):
            return ptype
    return ProductType.OTHER


class CardTraderCollector:
    name = SOURCE

    def __init__(self, client: CardTraderAPI | None = None, cfg: UserConfig | None = None) -> None:
        self.cfg = cfg or get_user_config()
        self.always_evaluate: set[tuple[str, int]] = set()
        self.client = client or get_cardtrader_client(self.cfg.sources.cardtrader.requests_per_second)
        self._game_id: int | None = None
        self._categories: dict[int, str] = {}

    # ------------------------------------------------------------------ catalogue
    @property
    def game_id(self) -> int:
        if self._game_id is None:
            for g in self.client.games():
                if "pokemon" in fold(f"{g.get('name', '')} {g.get('display_name', '')}"):
                    self._game_id = int(g["id"])
                    break
            else:
                raise RuntimeError("CardTrader: Pokémon game not found in /games")
        return self._game_id

    def category_name(self, category_id: int) -> str:
        if not self._categories:
            self._categories = {int(c["id"]): c["name"] for c in self.client.categories(self.game_id)}
        return self._categories.get(category_id, "")

    def tracked_expansions(self) -> list[tuple[dict[str, Any], SetMeta | None]]:
        ct = self.cfg.sources.cardtrader
        wanted: dict[str, SetMeta | None] = {}
        if ct.track_sets_from_config:
            for s in self.cfg.sets.sets:
                if s.cardtrader_track:
                    for key in (s.cardtrader_expansion, s.code, s.name):
                        if key:
                            wanted[fold(key)] = s
        for code in ct.extra_expansion_codes:
            wanted.setdefault(fold(code), None)
        out, seen = [], set()
        for exp in self.client.expansions():
            if exp.get("game_id") != self.game_id:
                continue
            for key in (fold(exp.get("code", "")), fold(exp.get("name", ""))):
                if key in wanted and exp["id"] not in seen:
                    out.append((exp, wanted[key]))
                    seen.add(exp["id"])
        return out

    def sync_catalog(self, session: Session) -> dict[int, tuple[str, int]]:
        """Upsert cards/products for tracked expansions. Returns blueprint_id → (entity_type, id)."""
        mapping: dict[int, tuple[str, int]] = {}
        for exp, meta in self.tracked_expansions():
            for bp in self.client.blueprints(exp["id"]):
                mapping[int(bp["id"])] = self._upsert_blueprint(session, bp, exp, meta)
        session.flush()
        log.info("cardtrader_catalog_synced", collector=SOURCE, items=len(mapping))
        return mapping

    def _upsert_blueprint(self, session: Session, bp: dict, exp: dict, meta: SetMeta | None) -> tuple[str, int]:
        bp_id = int(bp["id"])
        set_name = meta.name if meta else exp.get("name")
        set_code = meta.code if meta else (exp.get("code") or "").upper()
        release: date | None = meta.release_date if meta else None
        ptype = product_type_from(self.category_name(int(bp.get("category_id") or 0)), bp.get("name", ""))
        fixed = bp.get("fixed_properties") or {}
        if ptype is None:
            card = self._find_by_source_id(session, Card, bp_id) or self._adopt_card(
                session, bp["name"], set_code, fixed.get("collector_number"), bp_id)
            if card is None:
                card = Card(name=bp["name"], source_ids={SOURCE: bp_id})
                session.add(card)
            card.name = bp["name"]
            card.pokemon_name = pokemon_name_from(bp["name"])
            card.set_name, card.set_code, card.release_date = set_name, set_code, release
            card.card_number = fixed.get("collector_number") or card.card_number
            card.rarity = fixed.get("pokemon_rarity") or card.rarity
            card.image_url = bp.get("image_url") or card.image_url
            card.is_promo = "promo" in fold(f"{card.rarity or ''} {set_name or ''}")
            session.flush()
            return EntityType.CARD, card.id
        product = self._find_by_source_id(session, Product, bp_id)
        if product is None:
            product = Product(name=bp["name"], product_type=ptype, source_ids={SOURCE: bp_id})
            session.add(product)
        product.name, product.product_type = bp["name"], ptype
        product.set_name, product.set_code, product.release_date = set_name, set_code, release
        product.pack_count = product.pack_count or self.cfg.sets.pack_counts.get(ptype)
        product.image_url = bp.get("image_url") or product.image_url
        session.flush()
        return EntityType.PRODUCT, product.id

    @staticmethod
    def _adopt_card(session: Session, name: str, set_code: str | None, number: str | None, bp_id: int
                    ) -> Card | None:
        """Link a manually created / seeded card (no CardTrader id yet) instead of duplicating it."""
        if not (set_code and number):
            return None
        wanted = split_card_number(number)[0]
        for card in session.scalars(select(Card).where(Card.set_code == set_code)).all():
            if SOURCE in (card.source_ids or {}):
                continue
            if split_card_number(card.card_number)[0] == wanted and fold(card.name) == fold(name):
                card.source_ids = {**(card.source_ids or {}), SOURCE: bp_id}
                return card
        return None

    @staticmethod
    def _find_by_source_id(session: Session, model, bp_id: int):
        # JSON querying differs across SQLite/Postgres; the catalogue is small, so filter in Python.
        for row in session.scalars(select(model)).all():
            if (row.source_ids or {}).get(SOURCE) == bp_id:
                return row
        return None

    # ------------------------------------------------------------------ scan
    def _accept(self, p: dict) -> bool:
        ct = self.cfg.sources.cardtrader
        props = p.get("properties_hash") or {}
        lang = props.get("pokemon_language")
        if ct.languages and lang and lang not in ct.languages:
            return False
        cond = props.get("condition")
        if cond and ct.accepted_conditions and cond not in ct.accepted_conditions:
            return False
        if ct.exclude_graded and p.get("graded"):
            return False
        if p.get("on_vacation"):
            return False
        return (p.get("bundle_size") or 1) == 1

    def collect(self, session: Session) -> CollectorResult:
        result = CollectorResult()
        fx = get_rates(session)
        mapping = self.sync_catalog(session)
        self.always_evaluate = {(w.target_type, w.entity_id) for w in session.scalars(
            select(WatchlistItem).where(WatchlistItem.enabled.is_(True))).all()}
        ct = self.cfg.sources.cardtrader
        for exp, _meta in self.tracked_expansions():
            language = ct.languages[0] if len(ct.languages) == 1 else None
            data = self.client.marketplace_products(expansion_id=exp["id"], language=language)
            for bp_key, products in data.items():
                entity = mapping.get(int(bp_key))
                result.fetched += len(products)
                if not entity:
                    continue
                accepted = [p for p in products if self._accept(p)]
                result.matched += len(accepted)
                self._record(session, entity, accepted, fx, result)
        if self.client.is_mock:
            result.notes.append("MOCK data (no CARDTRADER_API_TOKEN configured)")
        return result

    def _record(self, session: Session, entity: tuple[str, int], products: list[dict], fx: FxRates,
                result: CollectorResult) -> None:
        if not products:
            return
        prices = [fx.to_nok(p["price"]["cents"] / 100, p["price"]["currency"]) for p in products]
        sellers = [str((p.get("user") or {}).get("id")) for p in products]
        stats = compute_stats(prices, sellers, self.cfg.scoring.fair_value.trim_fraction)
        record_snapshot(session, entity[0], entity[1], SOURCE, stats)
        self._backfill_card_props(session, entity, products[0])
        floor = self.cfg.sources.cardtrader.min_fair_value_to_evaluate_nok
        if (stats.trimmed_median or 0) < floor and entity not in self.always_evaluate:
            return  # bulk: keep the price history, skip deal evaluation
        n = self.cfg.sources.cardtrader.evaluate_cheapest_n
        cheapest = sorted(products, key=lambda p: p["price"]["cents"])[:n]
        for p in cheapest:
            listing = upsert_listing(session, self._raw(p, entity), fx)
            result.listing_ids.append(listing.id)

    def _raw(self, p: dict, entity: tuple[str, int]) -> RawListing:
        props = p.get("properties_hash") or {}
        user = p.get("user") or {}
        title = p.get("name_en", "")
        if props.get("collector_number"):
            title = f"{title} {props['collector_number']}"
        exp = p.get("expansion") or {}
        if exp.get("name_en"):
            title = f"{title} ({exp['name_en']})"
        return RawListing(
            source=SOURCE, external_id=str(p["id"]), title=title,
            asking_price=p["price"]["cents"] / 100, currency=p["price"]["currency"],
            url=f"https://www.cardtrader.com/cards/{p['blueprint_id']}",
            description=p.get("description"), seller=user.get("username"),
            condition=props.get("condition"), language=props.get("pokemon_language"),
            quantity=1, shipping_nok=self.cfg.sources.cardtrader.estimated_shipping_nok,
            is_graded=bool(p.get("graded")), known_entity=entity,
            listing_kind="sealed" if entity[0] == EntityType.PRODUCT else "single",
        )

    @staticmethod
    def _backfill_card_props(session: Session, entity: tuple[str, int], product: dict) -> None:
        if entity[0] != EntityType.CARD:
            return
        props = product.get("properties_hash") or {}
        card = session.get(Card, entity[1])
        if card:
            card.card_number = card.card_number or props.get("collector_number")
            card.rarity = card.rarity or props.get("pokemon_rarity")



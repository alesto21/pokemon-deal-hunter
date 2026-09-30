"""Configurable Norwegian store collectors.

The only adapter shipped in v1 is a generic Shopify adapter that reads the public
``/collections/<handle>/products.json`` endpoint many small web shops expose. It
is disabled by default; enable per shop in config/sources.yaml after checking the
shop's robots.txt and terms. robots.txt is enforced at runtime as well.

New store types: implement ``StoreAdapter.fetch()`` returning ``RawListing``s and
register them in ``ADAPTERS``.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from app.collectors.base import CollectorResult, RawListing, upsert_listing
from app.core.config import ShopConfig, get_user_config
from app.core.http import PoliteClient, robots_allowed
from app.core.logging import get_logger
from app.core.security import validate_url
from app.pricing.fx import get_rates

log = get_logger(__name__)


class StoreAdapter(Protocol):
    def fetch(self) -> list[RawListing]: ...


class ShopifyAdapter:
    MAX_PAGES = 4

    def __init__(self, shop: ShopConfig, rate: float, client: PoliteClient | None = None) -> None:
        self.shop = shop
        self.base = validate_url(shop.base_url).rstrip("/")
        self.client = client or PoliteClient(f"store:{shop.name}", rate)

    def _endpoint(self) -> str:
        if self.shop.collection:
            return f"{self.base}/collections/{self.shop.collection}/products.json"
        return f"{self.base}/products.json"

    def fetch(self) -> list[RawListing]:
        endpoint = self._endpoint()
        if not robots_allowed(endpoint):
            raise PermissionError(f"robots.txt does not allow {endpoint}")
        out: list[RawListing] = []
        for page in range(1, self.MAX_PAGES + 1):
            data = self.client.get(endpoint, params={"limit": 250, "page": page}).json()
            products = data.get("products", [])
            for p in products:
                variants = [v for v in p.get("variants", []) if v.get("available", True)]
                if not variants:
                    continue
                v = min(variants, key=lambda v: float(v.get("price") or 0))
                images = [i.get("src") for i in p.get("images", [])[:3] if i.get("src")]
                out.append(RawListing(
                    source=f"store:{self.shop.name}", external_id=str(v.get("id") or p.get("id")),
                    title=p.get("title", ""), asking_price=float(v.get("price") or 0),
                    currency=self.shop.currency, url=f"{self.base}/products/{p.get('handle')}",
                    seller=self.shop.name, shipping_nok=self.shop.estimated_shipping_nok,
                    seller_country=self.shop.country,
                    condition="Near Mint", image_urls=images,
                ))
            if len(products) < 250:
                break
        return out


ADAPTERS = {"shopify": ShopifyAdapter}


class StoreCollector:
    name = "stores"

    def collect(self, session: Session) -> CollectorResult:
        cfg = get_user_config().sources.stores
        result = CollectorResult()
        fx = get_rates(session)
        errors = []
        for shop in cfg.shops:
            if not shop.enabled:
                continue
            adapter_cls = ADAPTERS.get(shop.kind)
            if not adapter_cls:
                errors.append(f"{shop.name}: unknown adapter '{shop.kind}'")
                continue
            try:
                raws = adapter_cls(shop, cfg.requests_per_second).fetch()
            except Exception as exc:  # isolate shops from each other
                errors.append(f"{shop.name}: {type(exc).__name__}: {exc}")
                continue
            for raw in raws:
                if raw.asking_price <= 0:
                    continue
                listing = upsert_listing(session, raw, fx)
                result.fetched += 1
                if listing.matched_card_id or listing.matched_product_id:
                    result.matched += 1
                    result.listing_ids.append(listing.id)
        if errors:
            result.notes.extend(errors)
            if result.fetched == 0:
                raise RuntimeError("; ".join(errors))
        return result

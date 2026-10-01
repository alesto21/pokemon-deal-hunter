"""FINN.no manual ingestion adapter.

What IS supported:
* Adding individual FINN listing URLs you found yourself (CLI, API, dashboard).
* CSV / JSON import of listing URLs with price/title you provide.
* Optionally, ONE normal HTTP GET of that listing page — only if FINN's robots.txt
  allows our user agent — to read public metadata (title, price, image).

What is NOT supported (by design):
* Searching or crawling FINN, saved-search polling, logging in, bypassing any
  access controls, CAPTCHAs or rate limits. FINN does not offer private users a
  marketplace-wide API and we do not pretend otherwise.

A future ``FinnDiscovery`` implementation (e.g. an official partner feed or
saved-search e-mail parsing) can plug in via ``ListingDiscovery``.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy.orm import Session

from app.collectors.base import RawListing, upsert_listing
from app.collectors.finn_text import parse_shipping
from app.core.config import get_settings, get_user_config
from app.core.http import robots_allowed
from app.core.logging import get_logger
from app.core.security import sanitize_text, validate_url
from app.db.models import Listing
from app.pricing.fx import get_rates
from app.services.finn_analysis import analyse_finn_listing

log = get_logger(__name__)
SOURCE = "finn"
FINN_HOSTS = ("finn.no",)


class ListingDiscovery(Protocol):
    """Future hook: something that yields listing URLs without scraping search pages."""

    def discover(self) -> list[str]: ...


class FinnIngestError(ValueError):
    pass


def finn_code(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "finnkode" in qs:
        return qs["finnkode"][0]
    m = re.search(r"/(?:item|ad)/(\d{6,})", parsed.path) or re.search(r"(\d{7,})", parsed.path)
    if m:
        return m.group(1)
    raise FinnIngestError("Could not find a FINN code in the URL")


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.jsonld: list[str] = []
        self._in_ld = False
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "meta":
            key = a.get("property") or a.get("name") or a.get("itemprop")
            if key and a.get("content"):
                self.meta.setdefault(key.lower(), a["content"] or "")
        elif tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._in_ld = True
            self.jsonld.append("")
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_ld = False
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_ld:
            self.jsonld[-1] += data
        elif self._in_title:
            self.title += data


@dataclass
class PageMetadata:
    title: str | None = None
    description: str | None = None
    price: float | None = None
    currency: str | None = None
    image: str | None = None


def _to_price(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    s = re.sub(r"[^\d,.]", "", str(value)).replace(",", ".")
    try:
        return float(s) if s else None
    except ValueError:
        return None


def parse_listing_html(html: str) -> PageMetadata:
    p = _MetaParser()
    p.feed(html)
    md = PageMetadata(
        title=p.meta.get("og:title") or p.title.strip() or None,
        description=p.meta.get("og:description") or p.meta.get("description"),
        image=p.meta.get("og:image"),
        price=_to_price(p.meta.get("product:price:amount") or p.meta.get("og:price:amount")),
        currency=p.meta.get("product:price:currency") or p.meta.get("og:price:currency"),
    )
    for block in p.jsonld:
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            offers = item.get("offers") if isinstance(item, dict) else None
            if isinstance(offers, list):
                offers = offers[0] if offers else None
            if isinstance(offers, dict) and md.price is None:
                md.price = _to_price(offers.get("price"))
                md.currency = md.currency or offers.get("priceCurrency")
            if isinstance(item, dict) and not md.title and item.get("name"):
                md.title = item["name"]
    return md


def fetch_metadata(url: str, transport: httpx.BaseTransport | None = None) -> PageMetadata | None:
    """One polite request, only if robots.txt permits. Returns None when not allowed/failed."""
    if not robots_allowed(url):
        log.info("finn_fetch_skipped_robots", source=SOURCE, action="skip")
        return None
    try:
        with httpx.Client(timeout=15, follow_redirects=True, transport=transport,
                          headers={"User-Agent": get_settings().http_user_agent}) as client:
            resp = client.get(url)
        if resp.status_code != 200:
            log.info("finn_fetch_failed", source=SOURCE, status=resp.status_code)
            return None
        return parse_listing_html(resp.text[:2_000_000])
    except httpx.HTTPError as exc:
        log.info("finn_fetch_failed", source=SOURCE, error=type(exc).__name__)
        return None


def ingest_url(session: Session, url: str, title: str | None = None, price: float | None = None,
               currency: str = "NOK", shipping_nok: float | None = None, condition: str | None = None,
               description: str | None = None, seller: str | None = None, fetch: bool | None = None,
               location: str | None = None, seller_type: str | None = None, published_at=None,
               image_urls: list[str] | None = None, capture_method: str = "manual") -> Listing:
    """Add or update one FINN listing the user found (URL paste, CSV/JSON import or browser capture).

    Shipping: a value you give is exact; otherwise the listing text decides (stated amount →
    exact, "fri frakt" → included, "kun henting" → pickup); otherwise the configured default is
    used and labelled ESTIMATED. Afterwards the listing is analysed for lots and safety labels.
    """
    url = validate_url(url, FINN_HOSTS)
    code = finn_code(url)
    cfg = get_user_config().sources.finn
    md = None
    should_fetch = cfg.fetch_metadata if fetch is None else fetch
    if should_fetch and (title is None or price is None):
        md = fetch_metadata(url)
    title = title or (md.title if md else None)
    price = price if price is not None else (md.price if md else None)
    if not title or price is None:
        raise FinnIngestError(
            "Could not determine title/price automatically — please supply them (e.g. --title and --price)")
    description = description or (md.description if md else None)
    if shipping_nok is not None:
        ship_amount, ship_basis, pickup = shipping_nok, "exact", False
        ship_evidence = "entered by you"
    else:
        info = parse_shipping(f"{title}\n{description or ''}")
        pickup = info.kind == "pickup"
        if info.kind in ("exact", "included", "pickup"):
            ship_amount, ship_basis = info.amount_nok or 0.0, info.kind
        else:
            ship_amount, ship_basis = cfg.estimated_shipping_nok, "estimated"
        ship_evidence = info.evidence
    images = list(image_urls or []) or ([md.image] if md and md.image else [])
    raw = RawListing(
        source=SOURCE, external_id=code, url=url, title=title, asking_price=float(price),
        currency=(md.currency if md and md.currency and currency == "NOK" else currency) or "NOK",
        shipping_nok=ship_amount, shipping_known=ship_basis != "estimated", shipping_basis=ship_basis,
        seller_country="NO", description=description, seller=seller, condition=condition, image_urls=images,
        location=location, seller_type=seller_type, published_at=published_at, pickup_required=pickup,
        capture_method=capture_method,
    )
    listing = upsert_listing(session, raw, get_rates(session))
    listing.extracted = {**(listing.extracted or {}),
                         "shipping": {"basis": ship_basis, "amount_nok": ship_amount, "evidence": ship_evidence}}
    analyse_finn_listing(session, listing)
    return listing


def parse_import(content: str, filename: str = "import.csv") -> list[dict]:
    """Parse CSV (url,title,price,currency,shipping_nok,condition,description) or JSON list."""
    rows: list[dict]
    if filename.lower().endswith(".json") or content.lstrip().startswith("["):
        data = json.loads(content)
        if not isinstance(data, list):
            raise FinnIngestError("JSON import must be a list of objects")
        rows = [r for r in data if isinstance(r, dict)]
    else:
        rows = list(csv.DictReader(io.StringIO(content)))
    clean = []
    for r in rows[:1000]:
        clean.append({
            "url": (r.get("url") or "").strip(),
            "title": sanitize_text(r.get("title"), 500) or None,
            "price": _to_price(r.get("price")),
            "currency": (r.get("currency") or "NOK").strip().upper()[:3],
            "shipping_nok": _to_price(r.get("shipping_nok")),
            "condition": sanitize_text(r.get("condition"), 64) or None,
            "description": sanitize_text(r.get("description"), 4000) or None,
        })
    return clean

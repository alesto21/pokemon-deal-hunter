"""Estimated landed cost of a listing for a buyer in Norway.

landed_cost = item price + shipping (by seller region) + import buffer (by seller region)

The import buffer is a conservative *uncertainty* allowance for VAT, duty and carrier
handling on non-EEA purchases. It is not a tax calculation, and we never present it as one.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import SourcesConfig

OTHER = "other"


# Basis of a cost component. "exact" = stated by the seller or observed at a real checkout;
# "estimated" = from config (verify at checkout).
# "included" = shipping included in the price; "pickup" = buyer collects in person (no shipping
# cost, but not delivered — travel/meeting friction is NOT assumed to be zero, it is flagged).
EXACT, ESTIMATED, INCLUDED, PICKUP = "exact", "estimated", "included", "pickup"
_SHIPPING_CONF = {EXACT: 1.0, INCLUDED: 1.0, PICKUP: 0.7, ESTIMATED: 0.6}
_FEES_CONF = {EXACT: 1.0, ESTIMATED: 0.9}


def landed_confidence(shipping_basis: str, fees_basis: str) -> float:
    return round(min(_SHIPPING_CONF.get(shipping_basis, 0.6), _FEES_CONF.get(fees_basis, 0.9)), 2)


@dataclass(frozen=True)
class LandedCost:
    seller_country: str | None
    seller_region: str
    item_price_nok: float
    shipping_nok: float
    import_buffer_nok: float
    fees_nok: float = 0.0
    shipping_basis: str = ESTIMATED
    fees_basis: str = EXACT          # "exact" = no fees for this source
    route: str | None = None         # cardtrader: "direct" (seller ships) | "zero" (via CardTrader Zero hub)

    @property
    def landed_cost_nok(self) -> float:
        return round(self.item_price_nok + self.shipping_nok + self.fees_nok + self.import_buffer_nok, 2)

    @property
    def confidence(self) -> float:
        return landed_confidence(self.shipping_basis, self.fees_basis)


@dataclass(frozen=True)
class ShippingQuote:
    """An observed checkout: what one seller (route) really charged to ship to Norway."""

    shipment_nok: float
    fees_nok: float | None = None        # observed order fees for a single-card order, if known
    capacity_items: int | None = None    # "you can still add N items for the same shipping"


def region_for(country: str | None, cfg: SourcesConfig) -> str:
    code = (country or "").strip().upper()
    if not code:
        return OTHER
    for region, countries in cfg.region_countries.items():
        if code in (c.upper() for c in countries):
            return region
    return OTHER


def import_buffer(item_price_nok: float, region: str, cfg: SourcesConfig) -> float:
    buf = cfg.import_buffer_by_region.get(region)
    if buf is None:
        return 0.0
    return round(item_price_nok * buf.pct_of_item + buf.fixed_nok, 2)


def estimate_landed_cost(item_price_nok: float, country: str | None, cfg: SourcesConfig,
                         shipping_nok: float | None = None, shipping_known: bool = False,
                         shipping_basis: str | None = None) -> LandedCost:
    """Generic (non-CardTrader) landed cost. ``shipping_nok`` is the seller's stated shipping
    (``shipping_known=True``) or a configured source default (estimated). ``shipping_basis``
    may state it explicitly (exact | estimated | included | pickup)."""
    region = region_for(country, cfg)
    known = shipping_known and shipping_nok is not None
    if shipping_nok is None:
        shipping_nok = cfg.shipping_nok_by_region.get(region, cfg.shipping_nok_by_region.get(OTHER, 0.0))
    return LandedCost(
        seller_country=(country or "").upper() or None,
        seller_region=region,
        item_price_nok=round(item_price_nok, 2),
        shipping_nok=round(float(shipping_nok), 2),
        import_buffer_nok=import_buffer(item_price_nok, region, cfg),
        shipping_basis=shipping_basis or (EXACT if known else ESTIMATED),
    )


def cardtrader_fees(item_nok: float, cfg: SourcesConfig) -> float:
    """Estimated CardTrader order fees (fixed + % of the item subtotal). Calibrated on two observed
    checkouts (2026-10-01): $2.02 on a $15.90 item, $2.15 on a $34.94 item ≈ $1.91 + 0.7 %."""
    c = cfg.cardtrader_costs
    return round(c.fees_fixed_nok + c.fees_pct * item_nok, 2)


def cardtrader_landed_cost(item_price_nok: float, country: str | None, via_hub: bool, cfg: SourcesConfig,
                           quote: ShippingQuote | None = None) -> LandedCost:
    """Single-card delivered cost of a CardTrader listing.

    * direct seller: the seller ships one parcel to Norway (observed: $16.42 from Belgium).
    * CardTrader Zero (``can_sell_via_hub``): the item ships to the hub for free, then a separate
      final Zero shipment goes to Norway — a single-card purchase carries all of it.
    Without an observed checkout quote, shipping is ESTIMATED (conservative config values).
    """
    c = cfg.cardtrader_costs
    region = region_for(country, cfg)
    route = "zero" if via_hub else "direct"
    if quote is not None:
        shipping, s_basis = quote.shipment_nok, EXACT
    elif route == "zero":
        shipping, s_basis = c.zero_shipment_nok, ESTIMATED
    else:
        shipping, s_basis = c.direct_shipping_nok_by_region.get(region, c.direct_shipping_nok_by_region.get(
            OTHER, 300.0)), ESTIMATED
    if quote is not None and quote.fees_nok is not None:
        fees, f_basis = quote.fees_nok, EXACT
    else:
        fees, f_basis = cardtrader_fees(item_price_nok, cfg), ESTIMATED
    return LandedCost(
        seller_country=(country or "").upper() or None, seller_region=region,
        item_price_nok=round(item_price_nok, 2), shipping_nok=round(float(shipping), 2),
        import_buffer_nok=import_buffer(item_price_nok, region, cfg), fees_nok=round(fees, 2),
        shipping_basis=s_basis, fees_basis=f_basis, route=route,
    )


@dataclass(frozen=True)
class Basket:
    cards: int
    items_nok: float
    shipment_nok: float
    fees_nok: float
    import_nok: float
    total_nok: float
    shipping_per_card_nok: float
    landed_per_card_nok: list[float]
    over_capacity: bool


def basket_landed_cost(item_prices_nok: list[float], shipment_nok: float, cfg: SourcesConfig,
                       country: str | None = None, capacity_items: int | None = None,
                       fees_fixed_nok: float | None = None) -> Basket:
    """Several cards from ONE seller in one shipment: the shipment is paid once.

    basket landed = Σ items + one shipment + order fees (fixed once + % of subtotal) + import
    shipping_per_card = shipment / n. Each card's landed share = its price + equal shipping share
    + its share of fees/import. Groundwork for seller-basket opportunities — nothing is bought.
    """
    c = cfg.cardtrader_costs
    region = region_for(country, cfg)
    n = len(item_prices_nok)
    if n == 0:
        raise ValueError("a basket needs at least one item")
    items = sum(item_prices_nok)
    fixed = c.fees_fixed_nok if fees_fixed_nok is None else fees_fixed_nok
    fees = fixed + c.fees_pct * items
    imp = sum(import_buffer(p, region, cfg) for p in item_prices_nok)
    per_ship, per_fixed = shipment_nok / n, fixed / n
    per_card = [round(p + per_ship + per_fixed + c.fees_pct * p + import_buffer(p, region, cfg), 2)
                for p in item_prices_nok]
    return Basket(n, round(items, 2), round(shipment_nok, 2), round(fees, 2), round(imp, 2),
                  round(items + shipment_nok + fees + imp, 2), round(per_ship, 2), per_card,
                  bool(capacity_items and n > capacity_items + 1))


def region_allowed_for_deals(region: str | None, cfg: SourcesConfig) -> bool:
    return (region or OTHER) in cfg.deal_seller_regions

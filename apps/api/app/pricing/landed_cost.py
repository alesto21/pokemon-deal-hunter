"""Estimated landed cost of a listing for a buyer in Norway.

landed_cost = item price + shipping (by seller region) + import buffer (by seller region)

The import buffer is a conservative *uncertainty* allowance for VAT, duty and carrier
handling on non-EEA purchases. It is not a tax calculation, and we never present it as one.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import SourcesConfig

OTHER = "other"


@dataclass(frozen=True)
class LandedCost:
    seller_country: str | None
    seller_region: str
    item_price_nok: float
    shipping_nok: float
    import_buffer_nok: float

    @property
    def landed_cost_nok(self) -> float:
        return round(self.item_price_nok + self.shipping_nok + self.import_buffer_nok, 2)


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
                         shipping_nok: float | None = None) -> LandedCost:
    """``shipping_nok`` overrides the regional estimate (e.g. FINN shipping given by the seller)."""
    region = region_for(country, cfg)
    if shipping_nok is None:
        shipping_nok = cfg.shipping_nok_by_region.get(region, cfg.shipping_nok_by_region.get(OTHER, 0.0))
    return LandedCost(
        seller_country=(country or "").upper() or None,
        seller_region=region,
        item_price_nok=round(item_price_nok, 2),
        shipping_nok=round(float(shipping_nok), 2),
        import_buffer_nok=import_buffer(item_price_nok, region, cfg),
    )


def region_allowed_for_deals(region: str | None, cfg: SourcesConfig) -> bool:
    return (region or OTHER) in cfg.deal_seller_regions

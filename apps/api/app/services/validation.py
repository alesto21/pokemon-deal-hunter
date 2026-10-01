"""Final live validation of alert candidates against CardTrader's exact-blueprint endpoint.

The expansion-wide scan stays the cheap discovery mechanism. Before an alert is accepted, the
candidate is re-checked live with two requests made at the same moment:

* the exact ``marketplace/products?blueprint_id=…`` (the candidate must exist and be valid), and
* the same expansion request the scan uses (same currency view as price history), on which the
  whole chain re-runs: filters → market stats → fair value → score → alert policy.

The two endpoints present prices in different currencies with a cross-currency markup that is
uniform per seller region (observed 2026-10-01: blueprint=USD, expansion=EUR; EEA sellers ≈1.13,
US sellers ≈1.00). Absolute prices are therefore never compared across endpoints; listings are
compared to their own region's ratio instead.

* Candidate gone / no longer valid → ``stale`` (no alert).
* Endpoints disagree on the cheapest valid listings, a listing's price is inconsistent beyond
  the currency presentation, or the fresh fair value moved materially → ``conflict``: no alert,
  a ``MarketDataConflict`` with diagnostics is stored, nothing is "corrected".
* API failure → ``error`` (no alert: unvalidated alerts are never sent).

Fresh data decides the alert only; it is NOT written to price history.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import UserConfig
from app.core.http import RateLimiter
from app.core.logging import get_logger, redact_text
from app.db.base import utcnow
from app.db.models import Card, EntityType, Listing, MarketDataConflict, Product
from app.pricing.fair_value import CurrentMarket, estimate_fair_value
from app.pricing.fx import FxRates, get_rates
from app.scoring.context import EvaluationContext
from app.scoring.engine import ScoreResult, score_listing

log = get_logger(__name__)
_limiter: RateLimiter | None = None


@dataclass
class ValidationResult:
    status: str                       # ok | stale | conflict | error | unvalidated
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    ctx: EvaluationContext | None = None       # re-built on fresh data (status ok)
    result: ScoreResult | None = None          # re-scored on fresh data (status ok)

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "reason": self.reason, "checked_at": utcnow().isoformat(), **self.details}


def _rate_limited(cfg: UserConfig) -> None:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(cfg.alerts.live_validation.requests_per_second)
    _limiter.wait()


def blueprint_id(session: Session, listing: Listing) -> int | None:
    entity = session.get(Card, listing.matched_card_id) if listing.matched_card_id else (
        session.get(Product, listing.matched_product_id) if listing.matched_product_id else None)
    bp = (entity.source_ids or {}).get("cardtrader") if entity else None
    return int(bp) if bp else None


def _rows(verdicts, fx: FxRates, limit: int = 15) -> list[dict[str, Any]]:
    out = []
    for v in verdicts[:limit]:
        p, u = v.product, v.product.get("user") or {}
        out.append({"id": p.get("id"), "seller": u.get("username"), "country": u.get("country_code"),
                    "price": p["price"]["cents"] / 100, "currency": p["price"]["currency"],
                    "nok": fx.to_nok(p["price"]["cents"] / 100, p["price"]["currency"]),
                    "condition": (p.get("properties_hash") or {}).get("condition"),
                    "included": v.included, "reason": v.reason})
    return out


def _expansion_id(collector, session: Session, listing: Listing) -> int | None:
    entity = session.get(Card, listing.matched_card_id) if listing.matched_card_id else (
        session.get(Product, listing.matched_product_id) if listing.matched_product_id else None)
    if entity is None:
        return None
    for exp, meta in collector.tracked_expansions():
        if meta is not None and entity.set_code and meta.code.upper() == entity.set_code.upper():
            return int(exp["id"])
    return None


def _zone_ratios(exp_valid: dict, bp_valid: dict, fx: FxRates, cfg: UserConfig) -> dict[str, float]:
    """Median blueprint/expansion price ratio per seller region, from listings present in both.

    The two CardTrader endpoints present prices in different currencies and apply a
    cross-currency markup to sellers outside the response currency (observed: ~1.13 for EEA
    sellers, ~1.00 for US sellers when the blueprint response is USD and the expansion one EUR).
    That presentation effect is uniform per region; a listing deviating from its region's ratio
    is a genuine inconsistency (e.g. a stale cached price).
    """
    from statistics import median

    from app.pricing.landed_cost import region_for

    by_zone: dict[str, list[float]] = {}
    for pid, e in exp_valid.items():
        b = bp_valid.get(pid)
        if b is None:
            continue
        zone = region_for((e.product.get("user") or {}).get("country_code"), cfg.sources)
        e_nok = fx.to_nok(e.price_cents / 100, e.product["price"]["currency"])
        b_nok = fx.to_nok(b.price_cents / 100, b.product["price"]["currency"])
        if e_nok > 0:
            by_zone.setdefault(zone, []).append(b_nok / e_nok)
    return {z: round(median(v), 4) for z, v in by_zone.items()}


def validate_candidate(session: Session, listing: Listing, ctx: EvaluationContext, result: ScoreResult,
                       cfg: UserConfig, client=None) -> ValidationResult:
    """Re-check one alert candidate right now: exact blueprint + same-view expansion data."""
    from app.collectors.cardtrader import CardTraderCollector
    from app.pricing.landed_cost import region_for

    lv = cfg.alerts.live_validation
    bp = blueprint_id(session, listing)
    if bp is None:
        return ValidationResult("unvalidated", "no CardTrader blueprint to validate against")
    collector = CardTraderCollector(client=client, cfg=cfg)
    ct = cfg.sources.cardtrader
    language = ct.languages[0] if len(ct.languages) == 1 else None
    try:
        exp_id = _expansion_id(collector, session, listing)
        if exp_id is None:
            return ValidationResult("unvalidated", "card's set is not a tracked CardTrader expansion")
        _rate_limited(cfg)
        bp_rows = collector.client.marketplace_products(blueprint_id=bp, language=language).get(str(bp), [])
        _rate_limited(cfg)
        exp_rows = collector.client.marketplace_products(expansion_id=exp_id, language=language).get(str(bp), [])
    except Exception as exc:  # noqa: BLE001 — any failure means "not validated"
        return ValidationResult("error", f"live validation failed: {redact_text(type(exc).__name__)}")

    fx = get_rates(session)
    bp_verdicts, bp_stats = collector.market_stats(bp_rows, fx)
    exp_verdicts, exp_stats = collector.market_stats(exp_rows, fx)
    bp_valid = {str(v.product.get("id")): v for v in bp_verdicts if v.included}
    exp_valid = {str(v.product.get("id")): v for v in exp_verdicts if v.included}
    ratios = _zone_ratios(exp_valid, bp_valid, fx, cfg)

    def stats_dict(st, n_rows):
        return {"low": st.low, "cheapest3": st.cheapest3_median, "cheapest5": st.cheapest5_median,
                "cheapest10": st.cheapest10_median, "valid_listings": st.count,
                "excluded_listings": n_rows - st.count}

    scan_fv = ctx.fair_value.fair_value_nok if ctx.fair_value else None
    current = CurrentMarket(low=exp_stats.low, median=exp_stats.median, trimmed_median=exp_stats.trimmed_median,
                            cheapest5_median=exp_stats.cheapest5_median, listing_count=exp_stats.count,
                            dispersion=exp_stats.dispersion, cheapest3_median=exp_stats.cheapest3_median,
                            cheapest10_median=exp_stats.cheapest10_median,
                            has_expensive_tail=exp_stats.has_expensive_tail, low_is_outlier=exp_stats.low_is_outlier)
    fresh_fv = estimate_fair_value(current, ctx.history, cfg.scoring.fair_value, listing.confidence)
    details: dict[str, Any] = {
        "blueprint_id": bp, "expansion_id": exp_id,
        "scan": {"fair_value_nok": scan_fv, "item_price_nok": listing.normalized_price_nok},
        "blueprint_endpoint": {**stats_dict(bp_stats, len(bp_rows)),
                               "currencies": sorted({p["price"]["currency"] for p in bp_rows})},
        "fresh": {**stats_dict(exp_stats, len(exp_rows)), "fair_value_nok": fresh_fv.fair_value_nok,
                  "fair_value_confidence": fresh_fv.confidence, "flags": fresh_fv.flags,
                  "currencies": sorted({p["price"]["currency"] for p in exp_rows})},
        "zone_ratios": ratios,
        "cheapest_rows": {"blueprint": _rows(bp_verdicts, fx), "expansion": _rows(exp_verdicts, fx)},
    }

    # 1. the exact candidate must still be offered and valid on both endpoints
    item_nok = listing.normalized_price_nok
    if listing.source == "cardtrader":
        cid = listing.external_id
        on_bp = next((v for v in bp_verdicts if str(v.product.get("id")) == cid), None)
        on_exp = next((v for v in exp_verdicts if str(v.product.get("id")) == cid), None)
        if on_bp is None or on_exp is None:
            return ValidationResult("stale", "candidate listing no longer offered", details)
        if not (on_bp.included and on_exp.included):
            why = on_bp.reason or on_exp.reason
            return ValidationResult("stale", f"candidate listing no longer valid ({why})", details)
        item_nok = fx.to_nok(on_exp.price_cents / 100, on_exp.product["price"]["currency"])
        details["fresh"]["candidate_item_price_nok"] = item_nok

    # 2. both endpoints must agree on which listings make up the executable market
    exp_top = [v for v in exp_verdicts if v.included][:5]
    bp_top = [v for v in bp_verdicts if v.included][:5]
    missing = sorted({str(v.product["id"]) for v in bp_top} - set(exp_valid)) + \
        sorted({str(v.product["id"]) for v in exp_top} - set(bp_valid))
    if missing:
        return ValidationResult("conflict", f"endpoints disagree on cheapest valid listings ({len(missing)} "
                                            f"listing(s) only on one endpoint)", details | {"one_sided": missing})

    # 3. prices must be consistent once the per-region currency presentation is accounted for
    inconsistent = []
    for v in exp_top + ([on_exp] if listing.source == "cardtrader" else []):
        pid = str(v.product["id"])
        b = bp_valid.get(pid)
        zone = region_for((v.product.get("user") or {}).get("country_code"), cfg.sources)
        expected = ratios.get(zone)
        if b is None or not expected:
            continue
        ratio = fx.to_nok(b.price_cents / 100, b.product["price"]["currency"]) / fx.to_nok(
            v.price_cents / 100, v.product["price"]["currency"])
        if abs(ratio / expected - 1) > lv.price_tolerance:
            inconsistent.append({"id": pid, "zone": zone, "ratio": round(ratio, 4), "zone_ratio": expected})
    if inconsistent:
        details["inconsistent_listings"] = inconsistent
        return ValidationResult("conflict", f"{len(inconsistent)} listing price(s) inconsistent between "
                                            f"endpoints beyond the currency presentation", details)

    # 4. fresh fair value (same currency view as the scan and history) must not have moved materially
    if not fresh_fv.fair_value_nok:
        return ValidationResult("conflict", "no valid market on live validation", details)
    if scan_fv:
        fv_drift = abs(fresh_fv.fair_value_nok - scan_fv) / scan_fv
        details["fair_value_drift"] = round(fv_drift, 4)
        if fv_drift > lv.fair_value_tolerance:
            return ValidationResult("conflict", f"fair value moved {fv_drift:.0%} since the scan", details)

    fees = listing.fees_nok or 0.0
    if listing.fees_basis == "estimated":  # % part of the fee follows the fresh item price
        fees += cfg.sources.cardtrader_costs.fees_pct * (item_nok - listing.normalized_price_nok)
    landed = item_nok + listing.shipping_price_nok + fees + (listing.import_buffer_nok or 0.0)
    fresh_ctx = replace(ctx, fair_value=fresh_fv, listing_count=exp_stats.count, listing_price_nok=item_nok,
                        total_price_nok=round(landed, 2))
    return ValidationResult("ok", None, details, fresh_ctx, score_listing(fresh_ctx, cfg))


def active_conflict(session: Session, entity_type: str, entity_id: int, cfg: UserConfig) -> MarketDataConflict | None:
    """Manual conflicts stay until resolved; validation conflicts expire after ``conflict_ttl_hours``
    so the next candidate is re-validated (and re-flagged if the disagreement persists)."""
    ttl = timedelta(hours=cfg.alerts.live_validation.conflict_ttl_hours)
    for c in session.scalars(select(MarketDataConflict).where(
            MarketDataConflict.entity_type == entity_type, MarketDataConflict.entity_id == entity_id,
            MarketDataConflict.resolved_at.is_(None)).order_by(MarketDataConflict.detected_at.desc())).all():
        if c.source == "manual" or c.detected_at >= utcnow() - ttl:
            return c
    return None


def record_conflict(session: Session, listing: Listing, v: ValidationResult) -> MarketDataConflict:
    etype = EntityType.CARD if listing.matched_card_id else EntityType.PRODUCT
    eid = listing.matched_card_id or listing.matched_product_id
    conflict = MarketDataConflict(entity_type=etype, entity_id=eid, source="validation", reason=v.reason or "conflict",
                                  details={**v.details, "listing_id": listing.id})
    session.add(conflict)
    log.warning("market_data_conflict", listing_id=listing.id, match_id=eid, action="block", reason=v.reason)
    return conflict

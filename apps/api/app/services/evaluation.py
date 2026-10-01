"""Listing → context → score → (maybe) Telegram alert."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import UserConfig, get_user_config
from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.models import (
    Alert,
    Card,
    DealEvaluation,
    EntityType,
    Listing,
    PortfolioItem,
    Product,
    WatchlistItem,
)
from app.matching.normalize import fold
from app.notifications.formatting import format_deal_alert
from app.notifications.telegram import TelegramNotifier
from app.portfolio.modifiers import PortfolioState
from app.portfolio.service import graded_reference, portfolio_state_for_card
from app.pricing.fair_value import FAIR_VALUE_MODEL_VERSION, FairValue
from app.pricing.history import latest_snapshot
from app.scoring.context import EvaluationContext
from app.scoring.engine import ScoreResult, score_listing
from app.scoring.policy import AlertState, Decision, PreviousAlert, decide, effective_level
from app.services.lots import lot_for_listing, value_lot
from app.services.market import market_view
from app.services.validation import ValidationResult, active_conflict, record_conflict, validate_candidate

log = get_logger(__name__)

SOURCE_LABELS = {"cardtrader": "CardTrader", "finn": "FINN", "manual": "Manual"}


def is_premium_target(card: Card, cfg: UserConfig) -> bool:
    for t in cfg.pokemon.premium_targets:
        if fold(t.name) not in fold(card.name):
            continue
        if t.set_contains and fold(t.set_contains) not in fold(card.set_name or ""):
            continue
        if t.number and (card.card_number or "").split("/")[0].lstrip("0") != t.number.lstrip("0"):
            continue
        if t.rarity_contains and fold(t.rarity_contains) not in fold(card.rarity or ""):
            continue
        return True
    return False


def _watchlist(session: Session, etype: str, eid: int) -> WatchlistItem | None:
    return session.scalar(select(WatchlistItem).where(
        WatchlistItem.target_type == etype, WatchlistItem.entity_id == eid, WatchlistItem.enabled.is_(True)))


def _top_chase_value(session: Session, set_code: str | None) -> float | None:
    if not set_code:
        return None
    best = None
    for card in session.scalars(select(Card).where(Card.set_code == set_code)).all():
        snap = latest_snapshot(session, EntityType.CARD, card.id)
        if snap and snap.cheapest5_median and (best is None or snap.cheapest5_median > best):
            best = snap.cheapest5_median
    return best


def _loose_pack_value(session: Session, set_code: str | None) -> float | None:
    if not set_code:
        return None
    pack = session.scalar(select(Product).where(Product.set_code == set_code,
                                                Product.product_type == "booster_pack").limit(1))
    return market_view(session, EntityType.PRODUCT, pack.id).fair_value.fair_value_nok if pack else None


def build_context(session: Session, listing: Listing, cfg: UserConfig | None = None) -> EvaluationContext:
    cfg = cfg or get_user_config()
    ctx = EvaluationContext(
        source=listing.source, title=listing.title, total_price_nok=listing.scoring_price_nok,
        listing_price_nok=listing.normalized_price_nok, shipping_nok=listing.shipping_price_nok,
        import_buffer_nok=listing.import_buffer_nok or 0.0, seller_country=listing.seller_country,
        seller_region=listing.seller_region, fees_nok=listing.fees_nok or 0.0,
        shipping_basis=listing.shipping_basis or "estimated", fees_basis=listing.fees_basis or "exact",
        landed_cost_confidence=listing.landed_cost_confidence if listing.landed_cost_confidence is not None
        else 0.6, purchase_route=listing.purchase_route,
        listing_kind=listing.listing_kind, condition=listing.condition, description=listing.description,
        seller_rating=listing.seller_rating, match_confidence=listing.confidence, quantity=listing.quantity,
    )
    if listing.listing_kind == "lot":
        lot = lot_for_listing(session, listing.id)
        ctx.match_confidence = 1.0 if lot and lot.items else 0.0
        if lot and lot.items:
            valuation = value_lot(session, lot)
            ctx.fair_value = valuation.as_fair_value()
            ctx.lot_coverage, ctx.lot_unidentified = valuation.coverage, valuation.unidentified
        return ctx

    if listing.matched_card_id:
        card = session.get(Card, listing.matched_card_id)
        assert card is not None
        ctx.entity_type, ctx.entity_name = EntityType.CARD, card.name
        ctx.pokemon_name, ctx.rarity, ctx.card_number = card.pokemon_name, card.rarity, card.card_number
        ctx.set_code, ctx.set_name, ctx.release_date = card.set_code, card.set_name, card.release_date
        view = market_view(session, EntityType.CARD, card.id, listing.confidence)
        ctx.psa9_nok = graded_reference(session, card.id, 9)
        ctx.psa10_nok = graded_reference(session, card.id, 10)
        ctx.portfolio = portfolio_state_for_card(session, card, cfg)
        ctx.is_premium_target = is_premium_target(card, cfg)
        entity = (EntityType.CARD, card.id)
    elif listing.matched_product_id:
        product = session.get(Product, listing.matched_product_id)
        assert product is not None
        ctx.entity_type, ctx.entity_name = EntityType.PRODUCT, product.name
        ctx.product_type, ctx.pack_count = product.product_type, product.pack_count
        ctx.set_code, ctx.set_name, ctx.release_date = product.set_code, product.set_name, product.release_date
        view = market_view(session, EntityType.PRODUCT, product.id, listing.confidence)
        owned = session.scalar(select(func.coalesce(func.sum(PortfolioItem.quantity), 0))
                               .where(PortfolioItem.product_id == product.id)) or 0
        ctx.portfolio = PortfolioState(owned_quantity=int(owned))
        if product.product_type != "booster_pack":
            ctx.loose_pack_value_nok = _loose_pack_value(session, product.set_code)
        ctx.top_chase_value_nok = _top_chase_value(session, product.set_code)
        entity = (EntityType.PRODUCT, product.id)
    else:
        return ctx

    ctx.history, ctx.listing_count = view.history, view.current.listing_count
    ctx.fair_value = view.fair_value
    if listing.is_graded and listing.grade and ctx.entity_type == EntityType.CARD:
        # Graded listings are valued against graded references, never raw prices.
        ref = graded_reference(session, entity[1], listing.grade, listing.grade_company or "PSA")
        ctx.listing_kind = "graded"
        ctx.fair_value = (FairValue(ref, ref * 0.85, ref * 1.1, 0.6, [f"{listing.grade_company} {listing.grade:g} "
                                    f"manual reference"]) if ref else None)
    conflict = active_conflict(session, *entity, cfg)
    if conflict:
        ctx.market_conflict = f"{conflict.reason} ({conflict.source})"
    wl = _watchlist(session, *entity)
    if wl:
        ctx.watchlist_target_nok, ctx.watchlist_priority = wl.target_buy_price, wl.priority
    return ctx


def _alert_state(session: Session, listing: Listing, dry_run: bool) -> AlertState:
    """Cooldown and daily-cap state. Only alerts from the current mode count, so dry-run
    history never suppresses real alerts after Telegram is switched on."""
    prev = session.scalar(select(Alert).where(Alert.listing_id == listing.id, Alert.kind == "deal",
                                              Alert.dry_run.is_(dry_run))
                          .order_by(Alert.sent_at.desc()).limit(1))
    start_of_day = datetime.combine(utcnow().date(), datetime.min.time())
    today = session.scalar(select(func.count(Alert.id)).where(
        Alert.kind == "deal", Alert.sent_at >= start_of_day, Alert.severity != "STEAL",
        Alert.dry_run.is_(dry_run))) or 0
    entity_prev = None
    if listing.matched_card_id or listing.matched_product_id:
        same_entity = (select(Listing.id).where(Listing.matched_card_id == listing.matched_card_id)
                       if listing.matched_card_id else
                       select(Listing.id).where(Listing.matched_product_id == listing.matched_product_id))
        entity_prev = session.scalar(select(Alert).where(
            Alert.kind == "deal", Alert.dry_run.is_(dry_run), Alert.listing_id.in_(same_entity))
            .order_by(Alert.sent_at.desc()).limit(1))
    return AlertState(PreviousAlert(prev.sent_at, prev.price_nok) if prev else None,
                      PreviousAlert(entity_prev.sent_at, entity_prev.price_nok) if entity_prev else None,
                      today, utcnow())


def evaluate_listing(session: Session, listing: Listing, send_alerts: bool = True,
                     notifier: TelegramNotifier | None = None) -> tuple[DealEvaluation, ScoreResult, Decision | None]:
    cfg = get_user_config()
    ctx = build_context(session, listing, cfg)
    result = score_listing(ctx, cfg)
    effective = effective_level(result, cfg)  # always stored, even when alerts are off
    fv = ctx.fair_value
    reason = result.to_json()
    if listing.safety_flags:  # neutral "verify listing" labels from listing analysis
        reason["warnings"] = [*reason.get("warnings", []), *listing.safety_flags]
    if ctx.listing_kind == "lot":
        reason["lot"] = {"coverage": ctx.lot_coverage, "unidentified": ctx.lot_unidentified}
    reason["fair_value_explanation"] = fv.explanation if fv else []
    reason["history"] = ctx.history.__dict__
    reason["fair_value_flags"] = fv.flags if fv else []
    reason["fv_model"] = FAIR_VALUE_MODEL_VERSION
    reason["effective"] = {"raw_band": effective.raw_band, "level": effective.level, "caps": effective.caps}
    reason["landed_cost"] = {"item_price_nok": listing.normalized_price_nok,
                             "shipping_nok": listing.shipping_price_nok, "shipping_basis": listing.shipping_basis,
                             "fees_nok": listing.fees_nok or 0.0, "fees_basis": listing.fees_basis,
                             "import_buffer_nok": listing.import_buffer_nok or 0.0,
                             "landed_cost_nok": listing.scoring_price_nok,
                             "landed_cost_confidence": listing.landed_cost_confidence,
                             "purchase_route": listing.purchase_route,
                             "seller_country": listing.seller_country, "seller_region": listing.seller_region}
    ev = DealEvaluation(
        listing_id=listing.id, price_nok=listing.scoring_price_nok,
        fair_value_nok=fv.fair_value_nok if fv else None, fair_value_low=fv.fair_value_low if fv else None,
        fair_value_high=fv.fair_value_high if fv else None, fair_value_confidence=fv.confidence if fv else None,
        discount_pct=result.discount_pct,
        liquidity_score=result.components.get("liquidity", 0),
        popularity_score=result.components.get("pokemon_popularity", 0),
        set_score=result.components.get("set_desirability", 0),
        trend_score=result.components.get("trend", 0),
        grading_score=result.components.get("grading_upside", 0),
        scarcity_score=result.components.get("scarcity", 0),
        portfolio_score=result.portfolio_points,
        seller_confidence_score=result.seller_confidence,
        total_score=result.total_score, recommendation=result.recommendation, binder_fit=result.binder_fit,
        alert_level=effective.level,
        reason_json=reason,
    )
    session.add(ev)
    session.flush()
    decision = None
    if send_alerts and listing.status == "active":
        notifier = notifier or TelegramNotifier()
        state = _alert_state(session, listing, notifier.dry_run)
        decision = decide(ctx, result, state, cfg)
        decision, alert_ctx, alert_result, validation = confirm_alert(session, listing, ctx, result, decision,
                                                                      state, cfg)
        reason["notification"] = {"notify": decision.notify, "severity": decision.severity,
                                  "blocked_by": decision.blocked_by}
        if validation is not None:
            reason["validation"] = validation.as_dict()
        # The dict was already flushed; mutating it in place is invisible to SQLAlchemy.
        flag_modified(ev, "reason_json")
        if decision.notify and decision.severity:
            _send_alert(session, listing, ev, alert_ctx, alert_result, decision.severity, notifier)
    log.info("listing_evaluated", source=listing.source, listing_id=listing.id,
             match_id=listing.matched_card_id or listing.matched_product_id, score=result.total_score,
             action=result.recommendation)
    return ev, result, decision


def confirm_alert(session: Session, listing: Listing, ctx: EvaluationContext, result: ScoreResult,
                  decision: Decision, state: AlertState, cfg: UserConfig, persist: bool = True, client=None,
                  ) -> tuple[Decision, EvaluationContext, ScoreResult, ValidationResult | None]:
    """Final gate before an alert: validate the candidate live against its exact blueprint and
    re-run the decision on the fresh data. Non-candidates pass through untouched.

    ``persist=False`` (alert-preview) never writes conflicts.
    """
    if not (decision.notify and cfg.alerts.live_validation.enabled):
        return decision, ctx, result, None
    v = validate_candidate(session, listing, ctx, result, cfg, client=client)
    if not v.ok:
        if v.status == "conflict" and persist:
            record_conflict(session, listing, v)
        label = "market_data_conflict" if v.status == "conflict" else f"live validation {v.status}"
        return Decision(False, decision.severity, [f"{label}: {v.reason}"]), ctx, result, v
    assert v.ctx is not None and v.result is not None
    fresh = decide(v.ctx, v.result, state, cfg)
    if not fresh.notify:
        fresh.blocked_by = [f"no longer qualifies on live data: {b}" for b in fresh.blocked_by]
    return fresh, v.ctx, v.result, v


def _send_alert(session: Session, listing: Listing, ev: DealEvaluation, ctx: EvaluationContext,
                result: ScoreResult, severity: str, notifier: TelegramNotifier | None) -> Alert:
    notifier = notifier or TelegramNotifier()
    label = SOURCE_LABELS.get(listing.source, listing.source.replace("store:", "Store: "))
    text = format_deal_alert(ctx, result, severity, label)
    sent = notifier.send(text, listing.url)
    alert = Alert(deal_evaluation_id=ev.id, listing_id=listing.id, kind="deal", severity=severity,
                  price_nok=listing.scoring_price_nok, telegram_message_id=sent.message_id,
                  dry_run=sent.dry_run, message=text)
    session.add(alert)
    log.info("alert_sent" if sent.ok else "alert_failed", source=listing.source, listing_id=listing.id,
             score=result.total_score, action=severity, dry_run=sent.dry_run)
    return alert


def needs_evaluation(session: Session, listing: Listing, max_age_hours: float = 12) -> bool:
    last = session.scalar(select(DealEvaluation).where(DealEvaluation.listing_id == listing.id)
                          .order_by(DealEvaluation.timestamp.desc()).limit(1))
    if last is None:
        return True
    if (last.reason_json or {}).get("fv_model") != FAIR_VALUE_MODEL_VERSION:
        return True
    if abs(last.price_nok - listing.scoring_price_nok) > 0.5:
        return True
    return utcnow() - last.timestamp > timedelta(hours=max_age_hours)

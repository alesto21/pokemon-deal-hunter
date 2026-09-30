"""Command line interface: ``python -m app.cli <command>``."""

from __future__ import annotations

import json
import re
import secrets
from datetime import date
from pathlib import Path

import typer
from sqlalchemy import select

from app.core.config import REPO_ROOT, get_settings, get_user_config
from app.core.logging import configure_logging
from app.db.base import utcnow
from app.db.session import session_scope

cli = typer.Typer(help="Pokémon Deal Hunter", no_args_is_help=True, add_completion=False)


@cli.callback()
def _init() -> None:
    s = get_settings()
    configure_logging(s.log_level, s.log_json)


def _echo_json(data) -> None:
    typer.echo(json.dumps(data, indent=2, default=str, ensure_ascii=False))


@cli.command("scan-now")
def scan_now(source: str = typer.Option("cardtrader", help="cardtrader | stores | all"),
             alerts: bool = typer.Option(True, help="Send Telegram alerts for qualifying deals")) -> None:
    """Run collectors immediately (same code path as the scheduler)."""
    from app.services.scan import collector_factories, reevaluate_manual_listings, run_collector

    sources = list(collector_factories()) if source == "all" else [source]
    for src in sources:
        _echo_json(run_collector(src, send_alerts=alerts))
    typer.echo(f"re-evaluated manual listings: {reevaluate_manual_listings(send_alerts=alerts)}")


@cli.command("add-listing")
def add_listing(url: str, title: str = typer.Option(None), price: float = typer.Option(None),
                currency: str = "NOK", shipping: float = typer.Option(None, help="Shipping in NOK"),
                condition: str = typer.Option(None), no_fetch: bool = typer.Option(False, help="Never fetch the page"),
                alerts: bool = True) -> None:
    """Add a FINN listing URL (manual ingestion) and evaluate it."""
    from app.collectors.finn import ingest_url
    from app.services.evaluation import evaluate_listing

    with session_scope() as s:
        listing = ingest_url(s, url, title, price, currency, shipping, condition, fetch=False if no_fetch else None)
        ev, result, decision = evaluate_listing(s, listing, send_alerts=alerts)
        _print_eval(listing, ev, result, decision)


def _print_eval(listing, ev, result, decision) -> None:
    typer.echo(f"\n#{listing.id} [{listing.source}] {listing.title}")
    typer.echo(f"  match: {listing.match_status} ({listing.confidence:.2f}) → "
               f"card={listing.matched_card_id} product={listing.matched_product_id}")
    typer.echo(f"  seller: {listing.seller_country or '?'} ({listing.seller_region or '?'}) | item "
               f"{listing.normalized_price_nok:.0f} + shipping {listing.shipping_price_nok:.0f} + import buffer "
               f"{listing.import_buffer_nok or 0:.0f} = landed {listing.scoring_price_nok:.0f} NOK")
    typer.echo(f"  landed: {listing.scoring_price_nok:.0f} NOK | fair value: {ev.fair_value_nok or 0:.0f} NOK "
               f"(conf {ev.fair_value_confidence or 0:.2f}) | discount: {(ev.discount_pct or 0):.1%}")
    caps = (ev.reason_json.get("effective") or {}).get("caps", [])
    typer.echo(f"  score: {ev.total_score:.1f} (band {ev.recommendation}) → level {ev.alert_level}"
               f" | binder fit: {ev.binder_fit}")
    for cap in caps:
        typer.echo(f"   ↓ {cap}")
    for r in result.reasons:
        typer.echo(f"   + {r}")
    for w in result.warnings:
        typer.echo(f"   ! {w}")
    if decision:
        typer.echo(f"  notify: {decision.notify} ({decision.severity}) {'; '.join(decision.blocked_by)}")


@cli.command("evaluate-listing")
def evaluate_listing_cmd(listing_id: int, alerts: bool = typer.Option(False, help="Allow sending an alert")) -> None:
    """Re-evaluate one listing and print the full score breakdown."""
    from app.db.models import Listing
    from app.services.evaluation import evaluate_listing

    with session_scope() as s:
        listing = s.get(Listing, listing_id)
        if not listing:
            raise typer.BadParameter("listing not found")
        ev, result, decision = evaluate_listing(s, listing, send_alerts=alerts)
        _print_eval(listing, ev, result, decision)
        typer.echo("  components: " + ", ".join(f"{k}={v:.2f}" for k, v in result.components.items()))
        typer.echo("  modifiers:  " + (", ".join(f"{k}={v:+.1f}" for k, v in result.modifiers.items()) or "none"))


@cli.command("add-card")
def add_card(name: str = typer.Option(..., prompt=True), set_code: str = typer.Option(..., prompt=True),
             number: str = typer.Option(..., prompt="Card number (e.g. 177/162)"),
             rarity: str = typer.Option("", prompt=True), language: str = "en",
             pokemon: str = typer.Option(None, help="Pokémon name if different from card name")) -> None:
    """Add a card to the local catalogue."""
    from app.db.models import Card

    meta = get_user_config().sets.find(set_code)
    with session_scope() as s:
        card = Card(name=name, pokemon_name=pokemon or name, set_code=set_code.upper(),
                    set_name=meta.name if meta else set_code, card_number=number, rarity=rarity or None,
                    language=language, release_date=meta.release_date if meta else None, source_ids={})
        s.add(card)
        s.flush()
        typer.echo(f"card #{card.id} created: {card.name} {card.card_number} ({card.set_name})")


def _find_card(s, search: str):
    from app.db.models import Card

    like = f"%{search}%"
    rows = s.scalars(select(Card).where((Card.name.ilike(like)) | (Card.card_number.ilike(like))).limit(20)).all()
    if not rows:
        raise typer.BadParameter(f"no card matches '{search}'")
    if len(rows) == 1:
        return rows[0]
    for i, c in enumerate(rows, 1):
        typer.echo(f"  {i}. #{c.id} {c.name} {c.card_number} ({c.set_name}) {c.rarity or ''}")
    return rows[typer.prompt("Pick", type=int) - 1]


@cli.command("add-portfolio-item")
def add_portfolio_item(
    card_id: int = typer.Option(None), product_id: int = typer.Option(None),
    search: str = typer.Option(None, help="Search the catalogue by name/number instead of an id"),
    price: float = typer.Option(..., prompt="Purchase price per unit (NOK)"),
    quantity: int = 1, binder: str = typer.Option("regular", help="regular|premium|graded|sealed"),
    condition: str = "Near Mint", grading_status: str = "raw", grade_company: str = typer.Option(None),
    psa_grade: float = typer.Option(None), bought: str = typer.Option(None, help="YYYY-MM-DD"),
    notes: str = typer.Option(None),
) -> None:
    """Add a card or sealed product to your portfolio."""
    from app.db.models import PortfolioItem

    if binder not in ("regular", "premium", "graded", "sealed"):
        raise typer.BadParameter("binder must be regular|premium|graded|sealed")
    with session_scope() as s:
        if search:
            card_id = _find_card(s, search).id
        if not card_id and not product_id:
            raise typer.BadParameter("give --card-id, --product-id or --search")
        item = PortfolioItem(card_id=card_id, product_id=product_id, quantity=quantity, acquisition_price_nok=price,
                             acquisition_date=date.fromisoformat(bought) if bought else date.today(),
                             binder_type=binder, condition=condition, grading_status=grading_status,
                             grade_company=grade_company, psa_grade=psa_grade, notes=notes)
        s.add(item)
        s.flush()
        typer.echo(f"portfolio item #{item.id} added")


@cli.command("add-graded")
def add_graded(card_id: int, grade: float, price_nok: float, company: str = "PSA", confidence: float = 0.7,
               source: str = "manual") -> None:
    """Add/update a manual graded price reference (e.g. PSA 10)."""
    from app.api.routes.catalog import upsert_graded
    from app.api.schemas import GradedRefIn

    with session_scope() as s:
        ref = upsert_graded(s, GradedRefIn(card_id=card_id, grade_company=company, grade=grade, price_nok=price_nok,
                                           source=source, confidence=confidence))
        typer.echo(f"graded ref #{ref.id}: card {card_id} {company} {grade:g} = {price_nok:.0f} NOK")


@cli.command("test-telegram")
def test_telegram() -> None:
    """Send a test message (dry-run if Telegram is not configured)."""
    from app.notifications.telegram import TelegramNotifier

    n = TelegramNotifier()
    res = n.send("✅ <b>Pokémon Deal Hunter</b>: Telegram test message.")
    if res.dry_run:
        typer.echo("DRY-RUN: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set in .env — message was only logged.")
    elif res.ok:
        typer.echo(f"sent, message_id={res.message_id}")
    else:
        typer.echo(f"FAILED: {res.error}")
        raise typer.Exit(1)


@cli.command("backfill-prices")
def backfill_prices() -> None:
    """Refresh FX, sync the CardTrader catalogue and take a first price snapshot (no alerts)."""
    from app.pricing.fx import refresh_rates
    from app.services.scan import run_collector

    with session_scope() as s:
        try:
            rates = refresh_rates(s)
            typer.echo(f"FX: 1 EUR = {rates.nok_per_unit.get('EUR')} NOK")
        except Exception as exc:
            typer.echo(f"FX refresh failed ({type(exc).__name__}); fallback rates will be used")
    _echo_json(run_collector("cardtrader", send_alerts=False))


@cli.command("sync-catalog")
def sync_catalog() -> None:
    """Import cards/products of tracked sets from CardTrader."""
    from app.collectors.cardtrader import CardTraderCollector

    with session_scope() as s:
        mapping = CardTraderCollector().sync_catalog(s)
        typer.echo(f"{len(mapping)} blueprints synced")


def _cardtrader_expansion(c, set_code: str) -> dict:
    exps = [e for e, meta in c.tracked_expansions() if meta and meta.code.upper() == set_code.upper()]
    if not exps:
        raise typer.BadParameter(f"{set_code} is not a tracked set that CardTrader knows")
    return exps[0]


def _live_fair_value(session, entity: tuple[str, int] | None, stats):
    """Fair value from freshly fetched stats + our stored history (same code path as scoring)."""
    from app.pricing.fair_value import CurrentMarket, estimate_fair_value
    from app.pricing.history import HistoryStats, compute_history_stats, daily_series

    current = CurrentMarket(low=stats.low, median=stats.median, trimmed_median=stats.trimmed_median,
                            cheapest5_median=stats.cheapest5_median, listing_count=stats.count,
                            dispersion=stats.dispersion, cheapest3_median=stats.cheapest3_median,
                            cheapest10_median=stats.cheapest10_median,
                            has_expensive_tail=stats.has_expensive_tail, low_is_outlier=stats.low_is_outlier)
    history = compute_history_stats(daily_series(session, *entity, 90)) if entity else HistoryStats()
    return estimate_fair_value(current, history, get_user_config().scoring.fair_value), history


def _eur(v: float | None, eur_nok: float) -> str:
    return "-" if v is None else f"{v / eur_nok:7.2f}"


@cli.command("cardtrader-check")
def cardtrader_check(set_code: str = typer.Option("TEF", help="Set code from config/sets.yaml"),
                     top: int = typer.Option(15, help="How many of the most valuable cards to show")) -> None:
    """Sample CardTrader query: auth + one expansion's executable-market stats and fair values."""
    from app.collectors.cardtrader import CardTraderCollector
    from app.pricing.fx import get_rates

    c = CardTraderCollector()
    typer.echo(f"mode: {'MOCK' if c.client.is_mock else 'LIVE'} | info: {c.client.info().get('name')}")
    exp = _cardtrader_expansion(c, set_code)
    ct = get_user_config().sources.cardtrader
    data = c.client.marketplace_products(expansion_id=exp["id"],
                                         language=ct.languages[0] if len(ct.languages) == 1 else None)
    bps = {b["id"]: b for b in c.client.blueprints(exp["id"])}
    typer.echo(f"expansion {exp['name']} ({exp['code']}): {len(data)} blueprints with listings")
    with session_scope() as s:
        fx = get_rates(s)
        eur = fx.nok_per_unit["EUR"]
        rows = []
        for bp_id, products in data.items():
            verdicts, st = c.market_stats(products, fx)
            if st.count:
                rows.append((st.cheapest5_median or 0, bps.get(int(bp_id), {}), st, len(verdicts)))
        typer.echo(f"{'card':34} {'valid/all':>9} {'low':>7} {'c5':>7} {'c10':>7} {'trim':>7} {'FAIR':>7} "
                   f"{'conf':>5}  flags   (EUR; fair value uses stored history)")
        for _, bp, st, total in sorted(rows, key=lambda r: -r[0])[:top]:
            entity = c._find_entity(s, int(bp.get("id", 0)))
            fv, _ = _live_fair_value(s, entity, st)
            label = f"{bp.get('name', '?')} {bp.get('version') or ''}"[:34]
            typer.echo(f"{label:34} {st.count:>4}/{total:<4} {_eur(st.low, eur)} {_eur(st.cheapest5_median, eur)} "
                       f"{_eur(st.cheapest10_median, eur)} {_eur(st.trimmed_median, eur)} "
                       f"{_eur(fv.fair_value_nok, eur)} {fv.confidence:5.2f}  {','.join(fv.flags)}")


def _print_listing_rows(verdicts, fx, fair_value_nok: float | None) -> None:
    """One line per listing: pricing verdict plus landed cost and deal eligibility (seller region)."""
    from app.pricing.landed_cost import estimate_landed_cost, region_allowed_for_deals

    sources = get_user_config().sources
    typer.echo(f"{'listing':>10} {'seller':16} {'cc':2} {'region':11} {'lang':4} {'condition':13} "
               f"{'price':>8} {'cur':3} {'item':>6} {'ship':>4} {'imp':>4} {'landed':>6} {'disc':>6}  "
               f"{'fair-value use':15} {'deal region':11} reason")
    rank = 0
    for v in verdicts:
        p = v.product
        props, user = p.get("properties_hash") or {}, p.get("user") or {}
        cost = estimate_landed_cost(fx.to_nok(v.price_cents / 100, p["price"]["currency"]),
                                    user.get("country_code"), sources)
        disc = (f"{(fair_value_nok - cost.landed_cost_nok) / fair_value_nok:6.1%}" if fair_value_nok
                else "     -")
        tag = "no"
        if v.included:
            rank += 1
            tag = f"YES #{rank}" + (" c5" if rank <= 5 else " c10" if rank <= 10 else "")
        deal_ok = "ok" if region_allowed_for_deals(cost.seller_region, sources) else "blocked"
        typer.echo(f"{p['id']:>10} {str(user.get('username', ''))[:16]:16} {cost.seller_country or '??':2} "
                   f"{cost.seller_region:11} {str(props.get('pokemon_language')):4} "
                   f"{str(props.get('condition'))[:13]:13} {v.price_cents / 100:8.2f} {p['price']['currency']:3} "
                   f"{cost.item_price_nok:6.0f} {cost.shipping_nok:4.0f} {cost.import_buffer_nok:4.0f} "
                   f"{cost.landed_cost_nok:6.0f} {disc}  {tag:15} {deal_ok:11} {v.reason or ''}")


@cli.command("cardtrader-debug-card")
def cardtrader_debug_card(
    set_code: str = typer.Option(..., help="Set code from config/sets.yaml, e.g. TEF"),
    card_number: str = typer.Option(..., help="Collector number, e.g. 177 or 177/162"),
    all_languages: bool = typer.Option(False, help="Also fetch non-configured languages (shown as excluded)"),
    rows: bool = typer.Option(True, help="Print individual listings"),
) -> None:
    """Show every CardTrader listing for one card, whether it counts, why not, and the resulting fair value.

    Uses exactly the collector's request and filters, so the numbers match what scoring sees."""
    from app.collectors.cardtrader import CardTraderCollector, parse_version
    from app.matching.normalize import split_card_number
    from app.pricing.fx import get_rates

    c = CardTraderCollector()
    exp = _cardtrader_expansion(c, set_code)
    wanted = split_card_number(card_number)[0]
    matches = [b for b in c.client.blueprints(exp["id"])
               if split_card_number(parse_version(b.get("version"))[0]
                                    or (b.get("fixed_properties") or {}).get("collector_number"))[0] == wanted]
    if not matches:
        raise typer.BadParameter(f"no blueprint with number {card_number} in {exp['name']}")
    ct = get_user_config().sources.cardtrader
    language = None if all_languages or len(ct.languages) != 1 else ct.languages[0]
    # Same request as the collector (per expansion). CardTrader's per-blueprint endpoint returns
    # the same listings in a different display currency with a different cross-currency markup.
    data = c.client.marketplace_products(expansion_id=exp["id"], language=language)
    with session_scope() as s:
        fx = get_rates(s)
        eur = fx.nok_per_unit["EUR"]
        for bp in matches:
            products = data.get(str(bp["id"]), [])
            currencies = sorted({p["price"]["currency"] for p in products})
            if len(currencies) > 1:
                typer.echo(f"WARNING: mixed listing currencies {currencies}")
            verdicts, st = c.market_stats(products, fx)
            entity = c._find_entity(s, int(bp["id"]))
            typer.echo(f"\n=== {bp['name']} | version: {bp.get('version')} | blueprint {bp['id']} | "
                       f"{'MOCK' if c.client.is_mock else 'LIVE'} | 1 EUR = {eur:.4f} NOK"
                       f"{' (fallback rate!)' if fx.fallback else ''}")
            typer.echo(f"filters: languages={ct.languages} conditions={ct.accepted_conditions} "
                       f"graded={'excluded' if ct.exclude_graded else 'allowed'} "
                       f"reverse={'excluded' if ct.exclude_reverse_holo else 'allowed'} "
                       f"one-per-seller={ct.one_listing_per_seller}")
            fv, hist = _live_fair_value(s, entity, st)
            if rows:
                _print_listing_rows(verdicts, fx, fv.fair_value_nok)
            excluded: dict[str, int] = {}
            for v in verdicts:
                if not v.included:
                    key = v.reason.split(" ", 1)[0] if v.reason and v.reason.startswith(("language", "condition")) \
                        else v.reason or "?"
                    excluded[key] = excluded.get(key, 0) + 1
            typer.echo(f"\nlistings: {len(verdicts)} fetched, {st.count} valid, excluded: {excluded or 'none'}")
            typer.echo(f"fair value uses valid listings from ALL regions; alerts only for "
                       f"{get_user_config().sources.deal_seller_regions}; disc = vs fair value on landed cost")
            def line(name: str, v: float | None) -> None:
                typer.echo(f"  {name:22} {('-' if v is None else f'{v:8.0f} NOK'):>12}   {_eur(v, eur)} EUR")
            line("market_low", st.low)
            line("cheapest_3_median", st.cheapest3_median)
            line("cheapest_5_median", st.cheapest5_median)
            line("cheapest_10_median", st.cheapest10_median)
            line("broad_median", st.median)
            line("trimmed_median", st.trimmed_median)
            line("own_30d_median", hist.median_30d)
            line("FAIR VALUE", fv.fair_value_nok)
            line("fair_value_low", fv.fair_value_low)
            line("fair_value_high", fv.fair_value_high)
            typer.echo(f"  {'confidence':22} {fv.confidence:12.2f}")
            typer.echo(f"  {'market_has_expensive_tail':22} {st.has_expensive_tail!s:>12}")
            typer.echo(f"  {'lowest_listing_outlier':22} {st.low_is_outlier!s:>12}")
            typer.echo(f"  {'flags':22} {', '.join(fv.flags) or '-':>12}")
            for note in fv.explanation:
                typer.echo(f"    - {note}")


@cli.command("alert-preview")
def alert_preview(show_blocked: bool = typer.Option(True, help="Also list GOOD+ scores that would be blocked")) -> None:
    """Read-only: which active listings would alert on a fresh day (no cooldowns yet)? Writes nothing."""
    from app.api.routes.deals import latest_evaluations_query
    from app.db.models import DealEvaluation, Listing
    from app.scoring.engine import score_listing
    from app.scoring.policy import AlertState, PreviousAlert, decide, effective_level
    from app.services.evaluation import build_context

    cfg = get_user_config()
    with session_scope() as s:
        rows = s.execute(latest_evaluations_query().where(
            Listing.status == "active", DealEvaluation.recommendation.in_(["GOOD", "STRONG_BUY", "STEAL"]))
            .order_by(DealEvaluation.total_score.desc())).all()
        sent: dict[tuple, PreviousAlert] = {}
        capped = 0
        typer.echo(f"{len(rows)} active listings score GOOD or better. Simulating a fresh day "
                   f"(cap {cfg.alerts.max_alerts_per_day}/day, STEAL exempt):\n")
        for listing, _ev in rows:
            ctx = build_context(s, listing, cfg)
            result = score_listing(ctx, cfg)
            key = (listing.matched_card_id, listing.matched_product_id)
            d = decide(ctx, result, AlertState(previous_entity=sent.get(key), alerts_today=capped, now=utcnow()), cfg)
            eff = effective_level(result, cfg)
            fv = ctx.fair_value.fair_value_nok if ctx.fair_value else 0
            where = f"{listing.seller_country or '?'}/{listing.seller_region or '?'}"
            head = (f"{listing.title[:34]:34} {listing.source:10} {where:9} "
                    f"score {result.total_score:5.1f} (band {eff.raw_band})")
            costs = (f"item {listing.normalized_price_nok:.0f} + ship {listing.shipping_price_nok:.0f} + import "
                     f"{listing.import_buffer_nok or 0:.0f} = landed {listing.scoring_price_nok:.0f} NOK · "
                     f"fair value {fv or 0:.0f} · discount {(result.discount_pct or 0):.1%}")
            if d.notify:
                sent[key] = PreviousAlert(utcnow(), listing.scoring_price_nok)
                capped += d.severity != "STEAL"
                typer.echo(f"ALERT {d.severity:10} {head}\n      {costs}")
            elif show_blocked:
                typer.echo(f"  --  {eff.level:10} {head}\n      {costs}\n      blocked: {'; '.join(d.blocked_by)}")
            else:
                continue
            for cap in eff.caps:
                typer.echo(f"      ↓ {cap}")


@cli.command("purge-mock-data")
def purge_mock_data_cmd(yes: bool = typer.Option(False, "--yes", help="Skip confirmation")) -> None:
    """Remove mock CardTrader cards/listings/prices; move your watchlist/portfolio to the live cards."""
    from app.services.data_hygiene import purge_mock_data

    if not yes:
        typer.confirm("Delete all mock CardTrader data (user data is re-pointed to live cards)?", abort=True)
    with session_scope() as s:
        _echo_json(purge_mock_data(s))


@cli.command("reset-price-history")
def reset_price_history_cmd(yes: bool = typer.Option(False, "--yes", help="Skip confirmation")) -> None:
    """Delete price snapshots, daily aggregates and un-alerted evaluations (after a pricing-model change)."""
    from app.services.data_hygiene import reset_price_history

    if not yes:
        typer.confirm("Delete ALL price history? It is rebuilt from the next scans.", abort=True)
    with session_scope() as s:
        _echo_json(reset_price_history(s))


@cli.command("source-health")
def source_health() -> None:
    """Print collector health, scan-lock status and the next scheduled scan."""
    from app.api.routes.sources import source_health as health

    with session_scope() as s:
        for row in health(s):
            flag = {True: "OK ", False: "BAD", None: "OFF"}[row["healthy"]]
            typer.echo(f"[{flag}] {row['source']:10} mode={row['mode']:22} last_ok={row['last_success']} "
                       f"runs24h={row['runs_24h']} err_rate={row['error_rate_24h']} last_error={row['last_error']}")
            if row["kind"] != "scheduled":
                continue
            lock = row["scan_lock"]
            if lock["locked"]:
                typer.echo(f"      lock: HELD by {lock['owner']} since {lock['acquired_at']} "
                           f"(age {lock['age_seconds']}s, heartbeat {lock['heartbeat_age_seconds']}s ago, "
                           f"stale={lock['stale']})")
            else:
                typer.echo("      lock: free")
            w = row["worker"]
            if w["next_scan_overdue"]:
                typer.echo(f"      worker: OVERDUE — next scan was due {w['next_scheduled_scan']} UTC, "
                           f"{w['next_scan_overdue_seconds']:.0f}s ago (worker not running?)")
            elif w["next_scheduled_scan"]:
                typer.echo(f"      worker: scheduled — next scan {w['next_scheduled_scan']} UTC")
            else:
                typer.echo("      worker: not scheduled (worker stopped or source disabled)")
            typer.echo(f"      last successful scan: {w['last_successful_scan']}")


@cli.command("seed-watchlist")
def seed_watchlist_cmd() -> None:
    """Add the optional starter watchlist examples."""
    from app.seed import seed_watchlist

    with session_scope() as s:
        added = seed_watchlist(s)
    typer.echo("added: " + (", ".join(added) if added else "nothing (already present)"))


@cli.command("import-listings")
def import_listings(path: Path) -> None:
    """Import FINN listing URLs from CSV/JSON (url,title,price,currency,shipping_nok,condition,description)."""
    from app.collectors.finn import ingest_url, parse_import
    from app.services.evaluation import evaluate_listing

    rows = parse_import(path.read_text(encoding="utf-8-sig"), path.name)
    for r in rows:
        try:
            with session_scope() as s:
                listing = ingest_url(s, r["url"], r["title"], r["price"], r["currency"], r["shipping_nok"],
                                     r["condition"], r["description"])
                ev, *_ = evaluate_listing(s, listing)
                typer.echo(f"ok   #{listing.id} {listing.title[:50]} → {ev.total_score:.0f} {ev.alert_level}")
        except Exception as exc:
            typer.echo(f"fail {r['url']}: {exc}")


@cli.command("maintenance")
def maintenance() -> None:
    """Run daily housekeeping now (aggregates, retention, stale listings, portfolio snapshot)."""
    from app.services.maintenance import run_maintenance, snapshot_portfolio

    _echo_json(run_maintenance())
    snapshot_portfolio()


@cli.command("setup")
def setup() -> None:
    """Interactive first-run setup: writes .env and a few key preferences."""
    env_path = REPO_ROOT / ".env"
    current: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                current[k.strip()] = v.strip()
    typer.echo("Leave blank to keep the current value / use mock or dry-run mode.\n")

    def ask(key: str, prompt: str, secret: bool = False, default: str = "") -> None:
        shown = "(set)" if secret and current.get(key) else current.get(key, default)
        val = typer.prompt(f"{prompt} [{shown}]", default="", show_default=False, hide_input=secret)
        if val:
            current[key] = val
        elif key not in current:
            current[key] = default

    typer.echo("CardTrader: Profile → Settings → API (https://www.cardtrader.com/docs/api)")
    ask("CARDTRADER_API_TOKEN", "CardTrader API token", secret=True)
    typer.echo("Telegram: create a bot with @BotFather, then message it and open "
               "https://api.telegram.org/bot<TOKEN>/getUpdates to read your chat id")
    ask("TELEGRAM_BOT_TOKEN", "Telegram bot token", secret=True)
    ask("TELEGRAM_CHAT_ID", "Telegram chat id")
    current.setdefault("POSTGRES_PASSWORD", secrets.token_urlsafe(24))
    current.setdefault("API_KEY", secrets.token_urlsafe(32))
    example = (REPO_ROOT / ".env.example").read_text() if (REPO_ROOT / ".env.example").exists() else ""
    lines, seen = [], set()
    for line in example.splitlines():
        m = re.match(r"^([A-Z0-9_]+)=", line)
        if m and m.group(1) in current:
            lines.append(f"{m.group(1)}={current[m.group(1)]}")
            seen.add(m.group(1))
        else:
            lines.append(line)
    lines += [f"{k}={v}" for k, v in current.items() if k not in seen]
    env_path.write_text("\n".join(lines) + "\n")
    env_path.chmod(0o600)
    typer.echo(f"\nwrote {env_path} (mode 600)")

    cfg_dir = get_settings().config_dir
    _yaml_set(cfg_dir / "grading.yaml", "estimated_grading_cost_nok",
              typer.prompt("Estimated grading cost per card (NOK)", default="450"))
    _yaml_set(cfg_dir / "binders.yaml", "min_raw_value_nok",
              typer.prompt("Premium binder minimum raw value (NOK)", default="400"))
    _yaml_set(cfg_dir / "sources.yaml", "interval_minutes",
              typer.prompt("CardTrader scan interval (minutes, 15-60)", default="30"))
    _yaml_set(cfg_dir / "alerts.yaml", "max_alerts_per_day", typer.prompt("Max alerts per day", default="5"))
    typer.echo("Preferences saved in config/*.yaml (edit those files for everything else). Currency: NOK.")


def _yaml_set(path: Path, key: str, value: str) -> None:
    """Replace the first ``key: value`` in a YAML file while keeping comments intact."""
    if not re.fullmatch(r"\d+(\.\d+)?", value.strip()):
        raise typer.BadParameter(f"{key} must be a number")
    text = path.read_text()
    new, n = re.subn(rf"^(\s*{re.escape(key)}:\s*)[^\s#]+", rf"\g<1>{value.strip()}", text, count=1, flags=re.M)
    if n:
        path.write_text(new)


if __name__ == "__main__":
    cli()

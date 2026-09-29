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
    typer.echo(f"  total: {listing.total_price_nok:.0f} NOK | fair value: {ev.fair_value_nok or 0:.0f} NOK "
               f"(conf {ev.fair_value_confidence or 0:.2f}) | discount: {(ev.discount_pct or 0):.1%}")
    typer.echo(f"  score: {ev.total_score:.1f} → {ev.recommendation} | binder fit: {ev.binder_fit}")
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


@cli.command("cardtrader-check")
def cardtrader_check(set_code: str = typer.Option("TEF", help="Set code from config/sets.yaml")) -> None:
    """Sample CardTrader query: auth + one expansion's marketplace stats."""
    from app.collectors.cardtrader import CardTraderCollector
    from app.pricing.stats import compute_stats

    c = CardTraderCollector()
    typer.echo(f"mode: {'MOCK' if c.client.is_mock else 'LIVE'} | info: {c.client.info().get('name')}")
    typer.echo(f"pokemon game_id: {c.game_id}")
    exps = [e for e, meta in c.tracked_expansions() if meta and meta.code.upper() == set_code.upper()]
    if not exps:
        raise typer.BadParameter(f"{set_code} is not a tracked set that CardTrader knows")
    exp = exps[0]
    data = c.client.marketplace_products(expansion_id=exp["id"])
    bps = {b["id"]: b["name"] for b in c.client.blueprints(exp["id"])}
    typer.echo(f"expansion {exp['name']} ({exp['code']}): {len(data)} blueprints with listings")
    rows = []
    for bp_id, products in data.items():
        ok = [p for p in products if c._accept(p)]
        st = compute_stats([p["price"]["cents"] / 100 for p in ok])
        if st.count:
            rows.append((st.trimmed_median or 0, bps.get(int(bp_id), bp_id), st))
    for _, name, st in sorted(rows, key=lambda r: -r[0])[:10]:
        typer.echo(f"  {str(name)[:32]:32} n={st.count:3} low={st.low:7.2f} c5med={st.cheapest5_median:7.2f} "
                   f"trim={st.trimmed_median:7.2f} disp={st.dispersion if st.dispersion is not None else '-'} (EUR)")


@cli.command("source-health")
def source_health() -> None:
    """Print collector health."""
    from app.api.routes.sources import source_health as health

    with session_scope() as s:
        for row in health(s):
            flag = {True: "OK ", False: "BAD", None: "OFF"}[row["healthy"]]
            typer.echo(f"[{flag}] {row['source']:10} mode={row['mode']:22} last_ok={row['last_success']} "
                       f"runs24h={row['runs_24h']} err_rate={row['error_rate_24h']} last_error={row['last_error']}")


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
                typer.echo(f"ok   #{listing.id} {listing.title[:50]} → {ev.total_score:.0f} {ev.recommendation}")
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

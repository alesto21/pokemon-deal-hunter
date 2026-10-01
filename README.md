# Pokémon Deal Hunter

A self-hosted Pokémon TCG deal hunter and investment-binder assistant. It watches listings,
compares them with current and historical market prices, scores them with a transparent
configurable model, and sends a Telegram message **only** when something is genuinely attractive
for *your* binders.

- **Sources:** CardTrader (official API, primary pricing), FINN (user-driven: browser-capture bookmarklet at `/capture`, pasted URL, CSV — never crawled; see docs/SOURCES.md),
  opt-in Shopify web shops
- **Scoring:** discount vs a conservative fair value, liquidity, popularity, set desirability,
  trend, grading upside, scarcity, and portfolio/seller/match/lot modifiers
- **Portfolio:** regular / premium (GOD) / graded / sealed binders, valuation, duplicate
  awareness
- **Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL · APScheduler · Next.js ·
  Docker Compose
- **Runtime cost:** zero paid services. No LLM at runtime.

See [ARCHITECTURE.md](ARCHITECTURE.md), [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) (Proxmox) and
[docs/SOURCES.md](docs/SOURCES.md) (what each source can and cannot do).

## Quick start (Mac, Docker Desktop)

```bash
cp .env.example .env && chmod 600 .env
# set POSTGRES_PASSWORD and API_KEY to long random strings (or: see "First-run setup")
docker compose up -d --build
open http://localhost:3000
```

With no tokens set, the system runs end-to-end in **CardTrader MOCK mode** (sample data, clearly
labelled) and **Telegram dry-run** (alerts are logged, not sent).

Useful commands (inside the API container):
```bash
docker compose exec api python -m app.cli --help
docker compose exec api python -m app.cli scan-now                 # run a CardTrader scan now
docker compose exec api python -m app.cli seed-watchlist           # optional starter watchlist
docker compose exec api python -m app.cli add-listing "https://www.finn.no/recommerce/forsale/item/123456789" --title "Gastly 177/162" --price 625 --shipping 69
docker compose exec api python -m app.cli evaluate-listing 1
docker compose exec api python -m app.cli add-portfolio-item --search "Charizard" --price 1200 --binder premium
docker compose exec api python -m app.cli add-graded 1 10 5300    # card 1, PSA 10 = 5300 NOK
docker compose exec api python -m app.cli test-telegram
docker compose exec api python -m app.cli backfill-prices
docker compose exec api python -m app.cli source-health    # health, scan lock (owner/age/stale), next scan / OVERDUE
docker compose exec api python -m app.cli cardtrader-check --set-code TEF        # set overview with fair values
docker compose exec api python -m app.cli cardtrader-debug-card --set-code TEF --card-number 177   # every listing, used or why not
docker compose exec api python -m app.cli alert-preview      # read-only: what would alert on a fresh day
docker compose exec api python -m app.cli purge-mock-data    # after switching from mock to live
docker compose exec api python -m app.cli reset-price-history  # after a pricing-model change
docker compose exec api python -m app.cli market-conflict add --blueprint 258698 --reason "website shows offers the API lacks"
docker compose exec api python -m app.cli market-conflict list     # resolve with: market-conflict resolve <id>
docker compose exec api python -m app.cli shipping-quote add --seller PokeBilly --shipping 16.42 --fees 2.02 --currency USD --capacity 43
docker compose exec api python -m app.cli basket-preview <listing_id> --cards 1,2,5,10   # seller-basket economics
docker compose logs -f worker
```

## First-run setup

`python -m app.cli setup` (from `apps/api` with the venv, see below) walks you through:
- the CardTrader API token (CardTrader → profile → Settings → API)
- the Telegram bot token (@BotFather) and chat ID (`https://api.telegram.org/bot<TOKEN>/getUpdates`)
- generating `POSTGRES_PASSWORD` and `API_KEY`
- grading cost, premium-binder threshold, scan interval and daily alert cap (written to
  `config/*.yaml`)

Currency is NOK throughout. Everything else lives in `config/`:

| File | What |
|---|---|
| `pokemon.yaml` | popularity tiers, high-priority list, ignored Pokémon, themes, premium targets |
| `sets.yaml` | set desirability, aliases, release dates, which sets CardTrader tracks, pack counts |
| `rarities.yaml` | rarity → scarcity score, premium rarities |
| `binders.yaml` | premium/regular thresholds, portfolio modifiers |
| `scoring.yaml` | weights, curves, bands, modifiers, red-flag words, fair-value parameters |
| `alerts.yaml` | notification thresholds, daily cap, cooldowns, GOOD rules, digest |
| `grading.yaml` | grading cost (450 NOK), upside curve |
| `currencies.yaml` | FX source and fallback rates |
| `sources.yaml` | seller regions, deal regions, shipping and import buffers by region, source toggles, schedules, scan-lock timeouts (`scheduler.scan_lock_stale_minutes: 10`, `scan_lock_heartbeat_seconds: 60`) and worker-overdue detection (`scan_schedule_overdue_seconds: 120`), rate limits, retention |

Config files hot-reload. No restart needed, except for schedule changes (`docker compose restart worker`).
Restarting the worker is safe at any time: it lets a running scan finish (up to 60 s) before
exiting, and a restarted worker frees any lock its predecessor left behind. If the worker dies,
Sources/Overview show a red **WORKER OVERDUE** badge once its next scan is more than 2 minutes late.

## Environment variables (`.env`)

| Variable | Required | Purpose |
|---|---|---|
| `POSTGRES_PASSWORD` | ✅ | database password |
| `POSTGRES_USER`, `POSTGRES_DB` | – | default `dealhunter` |
| `API_KEY` | recommended | protects `/api/v1`. Only the web server sends it. |
| `CARDTRADER_API_TOKEN` | for live data | empty = mock mode |
| `CARDTRADER_MOCK` | – | `auto` (default) / `true` / `false` |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | for alerts | empty = dry-run |
| `TELEGRAM_DRY_RUN` | – | `auto` / `true` |
| `DASHBOARD_USER`, `DASHBOARD_PASSWORD` | recommended | HTTP basic auth on the dashboard |
| `BIND_ADDRESS` | – | host interface for published ports (default `127.0.0.1`) |
| `WEB_PORT`, `API_PORT` | – | default 3000 / 8000 |
| `LOG_LEVEL` | – | default INFO (containers log JSON) |

## Local development without Docker

```bash
cd apps/api
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
export DATABASE_URL=sqlite:///./dev.db
.venv/bin/alembic upgrade head
.venv/bin/python -m app.cli backfill-prices
.venv/bin/uvicorn app.api.main:app --reload            # http://localhost:8000/docs
.venv/bin/python -m app.worker                          # scheduler
.venv/bin/python -m pytest && .venv/bin/ruff check app tests
cd ../web && npm test && npm run lint && npm run build   # frontend unit tests (Node test runner), lint, build

cd ../web && npm install && API_INTERNAL_URL=http://localhost:8000 npm run dev
```

## Dashboard

A private, dark-first command center (desktop, tablet and iPhone). Open it via Tailscale, and
never expose it publicly.

| Group | Pages |
|---|---|
| — | **Overview**: portfolio KPIs (value, cost, P/L, raw/graded/sealed), best deals right now, scanner status, portfolio charts |
| Trading | **Deals** (filters, deal detail: price → market → decision), **Watchlist** (targets, best listing, sparkline), **Portfolio** (holdings, add/edit) |
| Collection | **GOD Binder** (216 pockets), **Collection** (360 pockets), **Sealed** (per-pack economics, rip/hold scores), **Grading** (candidates → submitted → at grader → returned; PSA 9/10 economics) |
| Market | **Market** (coverage, movers, liquidity, strongest discounts, price chart per card), **Alerts** (sent + held back with reasons), **Listings** (browse + match review) |
| System | **Sources**, **System** (worker, lock, database, Telegram, backups, FX), **Settings** |

Badges always show the **effective level** (after caps); the raw score and band are shown
separately. Every number is real. Where history or PSA data does not exist yet, pages say so
instead of estimating. On phones there is a bottom tab bar, and tables become cards.
Binder capacities are set in `config/binders.yaml` (`capacity_slots`).

## How alerts are decided (short version)

1. Fair value = the **buyable** market: 60% cheapest-5 median + 25% cheapest-10 median + 15% own
   30-day median, over valid listings only (English, NM, raw, not reverse holo, one per seller).
   Stale expensive asks are ignored, and one cheap listing can't define it. Confidence drops when
   data is thin, dispersed or volatile.
2. Every listing gets a single-card **landed cost** = item + shipping + fees + import buffer. On
   CardTrader, shipping depends on the route (direct seller parcel vs CardTrader Zero) and is an
   **estimate** unless you recorded an observed checkout quote for the seller. Discount, score and
   recommendation use the landed cost, never the sticker price. Cheap item ≠ cheap delivered.
3. Score = weighted components + modifiers, which gives a raw **score band**: IGNORE / WATCH /
   GOOD / STRONG BUY / STEAL.
4. The **effective level** is the band after caps, and it is what the dashboard badge and Telegram
   show. The alert severity is capped by the actual discount (15 / 22 / 30%). An item priced over 45%
   below fair value is capped at STRONG BUY with a "verify listing" warning, because such listings
   are usually stale or mispriced.
5. Every alert candidate is **validated live** against the exact CardTrader blueprint just before
   sending. A stale listing, an endpoint disagreement or an open `market_data_conflict` blocks it.
6. Hard filters: seller in `deal_seller_regions` (default EEA only), fair value ≥ 250 NOK, match confidence ≥ 0.9, fair-value confidence ≥ 0.5,
   sensible condition, no duplicates without a > 35% discount, no re-alert for the same listing
   **or the same card** without a real price drop, max 5/day (STEAL exempt). Dry-run and live
   alerts are counted separately.

A 30% discount on a 30 NOK card never notifies you. See ARCHITECTURE.md for the details.

## Status

See [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md) for what works now and the phase-2 backlog.

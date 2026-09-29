# Pokémon Deal Hunter

A self-hosted Pokémon TCG deal hunter and investment-binder assistant. It watches listings,
compares them with current and historical market prices, scores them with a transparent
configurable model, and sends a Telegram message **only** when something is genuinely attractive
for *your* binders.

- **Sources:** CardTrader (official API, primary pricing), FINN (manual URL / CSV ingestion),
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
docker compose exec api python -m app.cli source-health
docker compose exec api python -m app.cli cardtrader-check --set-code TEF
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
| `sources.yaml` | source toggles, schedules, rate limits, retention |

Config files hot-reload. No restart needed, except for schedule changes (`docker compose restart worker`).

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

cd ../web && npm install && API_INTERNAL_URL=http://localhost:8000 npm run dev
```

## Dashboard

Overview · Deals (filters, reasoning, add/import FINN listings, lots) · Watchlist · Portfolio ·
Price history · Match review · Sources · Collector health · Settings.

## How alerts are decided (short version)

1. Fair value = blend of the trimmed current median and the cheapest-5 median, blended with our own
   30-day median. Confidence drops when data is thin, dispersed or volatile. **Never just the
   cheapest listing.**
2. Score = weighted components + modifiers, which gives IGNORE / WATCH / GOOD / STRONG BUY / STEAL.
3. The alert severity is capped by the actual discount (15 / 22 / 30%).
4. Hard filters: fair value ≥ 250 NOK, match confidence ≥ 0.9, sensible condition, no duplicates
   without a > 35% discount, no re-alerts without a real price drop, max 5/day (STEAL exempt).

A 30% discount on a 30 NOK card never notifies you. See ARCHITECTURE.md for the details.

## Status

See [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md) for what works now and the phase-2 backlog.

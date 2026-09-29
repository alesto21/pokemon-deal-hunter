# Architecture

## Overview

```
                ┌────────────────────── Docker Compose (Ubuntu VM on Proxmox) ──────────────────────┐
 Browser ──►    │  web (Next.js)  ──/api/proxy + X-API-Key──►  api (FastAPI)  ──►  postgres           │
 (Tailscale)    │                                                    ▲                   ▲              │
                │  worker (APScheduler) ── collectors ── pricing ── scoring ── alerts ──┘              │
                │        │                                                     │                       │
                │        ├─► CardTrader API v2 (Bearer token)                   └─► Telegram Bot API   │
                │        ├─► Frankfurter FX (daily, free)                                              │
                │        └─► Shopify stores (opt-in, robots.txt enforced)                              │
                │  backup (prod only) ── pg_dump daily → ./backups (7 daily + 4 weekly)                │
                └──────────────────────────────────────────────────────────────────────────────────────┘
```

* **api** and **worker** run the same Python image with different commands; `migrate` is a
  one-shot container that runs `alembic upgrade head` before either starts.
* **web** never talks to the API from the browser. A Next.js route handler (`/api/proxy/*`) adds the
  API key server-side. The browser only ever sees the web container.
* No Redis/Celery: one scheduler process with `max_instances=1` per job plus a DB row lock per
  source (`source_status.running_since`) is enough for a few requests every 30 minutes.

## Repository layout (and why it differs from the suggested one)

```
apps/api/            Python project (one package: app/)
  app/core/          settings (.env) + YAML user config, logging/redaction, polite HTTP, URL validation
  app/db/            SQLAlchemy models, session
  app/collectors/    source adapters: cardtrader (+mock), finn (manual), stores (Shopify), base upsert
  app/matching/      title parsing + card/product matcher with confidence bands
  app/pricing/       stats, fair value, history/aggregates/retention, FX, grading, sealed
  app/scoring/       evaluation context, scoring engine, notification policy
  app/notifications/ Telegram client + message formatting
  app/portfolio/     portfolio modifiers + valuation
  app/services/      orchestration: evaluate listing, run collector + health, maintenance, lots
  app/api/           FastAPI app, routes, schemas
  app/cli.py         `python -m app.cli …`
  app/worker.py      scheduler entrypoint
  alembic/           migrations
  tests/             pytest suite + fixtures
apps/web/            Next.js dashboard
config/              user-editable YAML (hot-reloaded)
infra/backup/        backup scripts used by the backup container
scripts/             backup-now / restore helpers
docs/                deployment, sources, examples
```

The brief suggested `services/collectors`, `services/pricing`, `services/scoring`,
`services/notifications` and `packages/shared` as separate top-level folders. They share the same
models, config and DB session and ship in the same image, so separate top-level Python packages
would only add `sys.path` hacks or several pip packages. They are subpackages of `apps/api/app/`
with the same boundaries. Collectors stay isolated from each other: a collector only produces
`RawListing`s and snapshots, and nothing else imports a specific collector.

## Data flow for one scan

1. `worker` → `services.scan.run_collector("cardtrader")` takes the source lock.
2. `CardTraderCollector.sync_catalog` upserts cards/products for tracked sets (`config/sets.yaml`).
3. One `GET /marketplace/products?expansion_id=…&language=en` per set. Listings are filtered
   (language, NM/Mint, not graded, not on vacation, single copies). Prices are converted to NOK.
4. `compute_stats` → `PriceSnapshot` (low, median, trimmed median, cheapest-5 median, count,
   seller count, dispersion).
5. The cheapest N listings per item become `Listing`s (bulk under
   `min_fair_value_to_evaluate_nok` is priced but never evaluated, unless it is on the watchlist).
6. `services.evaluation.evaluate_listing`: build context (fair value, history, PSA refs, portfolio,
   watchlist), then `score_listing`, then `DealEvaluation`, then `policy.decide`, then maybe Telegram → `Alert`.
7. Unseen listings are marked `gone`. Today's `PriceDaily` aggregate is refreshed.
8. `CollectorRun` + `SourceStatus` are updated. After N consecutive failures, ONE health alert is
   sent, and a recovery message follows the next success.
9. Active FINN/manual listings are re-scored against the fresh fair values (no network).

## Fair value (`pricing/fair_value.py`)

* ≥3 listings: `0.6 × trimmed median + 0.4 × cheapest-5 median` (the trimmed median drops the top
  20% of asks).
* Own 30-day median available (≥5 days): blended in with weight 0.4.
* Falling market (30d trend < −5%): use the lower current value.
* Confidence is multiplied down for few listings, dispersion > 0.5, volatility > 0.15, missing
  history and identity confidence < 1. The low–high band widens accordingly.
* Graded listings are valued only against manual graded references, never raw prices.
* Lots: conservative value = Σ(item low fair value) × 0.85, with confidence tied to how many items
  are priced.

## Scoring (`scoring/engine.py`)

Weighted components (0..1 × weight, defaults in `config/scoring.yaml`): discount 30 (scaled by
fair-value confidence), liquidity 20, Pokémon popularity 15, set desirability 10, trend 10,
grading upside 10 (for sealed products this is the sealed-hold score), scarcity 5.

Modifiers (points): portfolio (duplicate −8/−4, missing high-priority +8, iconic missing +5,
theme +5, diversification +3, bonus capped at +15), seller confidence (up to −12, red-flag words),
match confidence (−5 per 0.1 below 0.9), lot −8, multi-item −3, watchlist target met +8,
high-priority watch +3, premium value +3.

Bands: 0–59 IGNORE, 60–74 WATCH, 75–84 GOOD, 85–92 STRONG BUY, 93–100 STEAL.

## Notification policy (`scoring/policy.py`)

The alert severity is the lower of two levels: the score band, and the level the raw discount
supports (15/22/30%). A STEAL score with an 18% discount therefore alerts as GOOD. Hard filters:
fair value ≥ 250 NOK (unless the item is on the high-priority watchlist), match confidence ≥ 0.90,
fair-value confidence ≥ 0.5, no damaged/played condition, not an ignored Pokémon, no duplicate
unless the discount is > 35%, seller confidence ≥ 0.3. GOOD also needs a special rule (watchlist
target met / high-priority missing / premium fit). No re-alert for the same listing unless 24 h
have passed AND the price dropped ≥ 10%. At most 5 alerts/day, and STEAL ignores the cap.

## Matching (`matching/`)

A deterministic parser extracts the number/printed total, set (via aliases, or inferred from the
printed total), product type (EN + NO keywords), lot words, language, grade and condition. Card
score is built from: number+total 0.45, set 0.2, fuzzy name 0.35 (rapidfuzz token-set), minus
penalties for mismatches and the wrong language. When the top two candidates are within 0.05, the
match can never auto-accept. ≥0.90 auto, 0.70–0.89 review, <0.70 unresolved. The dashboard review
screen resolves the rest.

## Price history and retention

Raw `price_snapshots` are kept for 30 days, and `price_daily` aggregates are kept forever. The
7/30/90-day and all-time medians, trend (first vs last quarter of the 30-day window) and
volatility (stdev of daily log returns) are computed from the daily aggregates. Collector runs are
kept for 30 days. Deal evaluations without alerts are kept for 90 days.

## Security

* Secrets live only in `.env` (git-ignored, chmod 600 via `setup`). Settings use `SecretStr`, and
  `/settings` reports only whether a secret is set.
* Log redaction covers keys named token/secret/password/api_key/authorization/chat_id and
  Telegram/Bearer token patterns in free text. httpx request logging is silenced (Telegram URLs
  contain the token).
* `/api/v1/*` requires `X-API-Key` when `API_KEY` is set, and only the web server knows it. Optional
  basic auth protects the dashboard.
* Ports bind to `127.0.0.1` by default. In prod the API has no published port at all.
* URL validation: http(s) only, no credentials, no private/loopback hosts, FINN host allow-list.
  Imported text is NFKC-normalised, stripped of control characters and length-capped. Uploads are
  checked by magic bytes and size, and stored under random names.
* Containers run as non-root users.

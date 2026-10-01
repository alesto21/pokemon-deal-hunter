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
* Scans are protected by a per-source **scan lock** with owner, heartbeat and stale timeout (see
  "Scan locks and graceful shutdown" below).
* **web** never talks to the API from the browser. A Next.js route handler (`/api/proxy/*`) adds the
  API key server-side. The browser only ever sees the web container.
* No Redis/Celery: one scheduler process with `max_instances=1` per job plus a DB row lock per
  source (`source_status`) is enough for a few requests every 30 minutes.

## Repository layout (and why it differs from the suggested one)

```
apps/api/            Python project (one package: app/)
  app/core/          settings (.env) + YAML user config, logging/redaction, polite HTTP, URL validation
  app/db/            SQLAlchemy models, session
  app/collectors/    source adapters: cardtrader (+mock), finn (user-driven capture; finn_text = shipping/lot text analysis), stores (Shopify), base upsert
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

## Dashboard read models (`services/dashboard.py`, `/api/v1/dashboard/*`)

Every dashboard page makes one call to a read-only aggregation endpoint: `overview`, `deals` (+
`deals/{listing_id}`), `portfolio`, `binder/{premium|regular}`, `sealed`, `grading`,
`watchlist`, `market` (+ `market/series/{type}/{id}`), `alerts` and `system`. They only *read*.
Values come from the database or from existing domain functions (fair value, grading economics,
sealed analysis, effective level), so the UI never re-implements pricing.

* **No fabricated data:** where history, a PSA reference or a market price does not exist, the
  field is `null` / `ready: false` and the UI shows an empty state. Movers need ≥2 collected
  days. Portfolio charts need ≥2 non-empty daily snapshots. Fair value "over time" is the daily
  median of the fair values the scorer actually stored on evaluations.
* Badges, filters and counts use the **effective level** (after caps).
* Binder capacities come from `config/binders.yaml` (`capacity_slots`: GOD 216, regular 360).
  Grading workflow statuses: `raw` (candidate) → `submitted` → `at_grader` → `graded` (returned).
* The System page reads backup status from `BACKUP_DIR`. The prod overlay mounts `./backups`
  read-only into the API for this.

The Next.js dashboard is dark-first, grouped by Trading / Collection / Market / System, with a
bottom tab bar and drawer on phones. Tables become cards below the `md` breakpoint.

## Scan locks and graceful shutdown (`services/locks.py`, `worker.py`)

The worker's scheduled scans and manual "Run now" / `scan-now` share one lock per source in
`source_status`:

| Column | Meaning |
|---|---|
| `running_since` | lock acquired at |
| `lock_owner` | `role@hostname#pid-instance`, unique per process start (`worker@dealhunter-worker#1-6b7cba43`) |
| `lock_heartbeat_at` | refreshed every `scan_lock_heartbeat_seconds` (60 s) by a background thread while scanning |
| `next_run_at` | next scheduled scan, written by the worker (after each job and every minute) in database time; null = not scheduled |

* **Time:** every lock timestamp, age, stale check and schedule check uses the **database clock**
  (`db/clock.py::db_now`: `clock_timestamp()` on Postgres). Process clock skew cannot make a lock
  look fresh or stale. The worker converts its next run to database time (DB now + time until
  the job fires).
* **Acquire:** one atomic conditional UPDATE. It succeeds only if the lock is free or its last
  heartbeat is older than `scan_lock_stale_minutes` (10). A long but alive scan keeps
  heartbeating and is never reclaimed. Reclaiming is logged as `stale_lock_reclaimed`.
* **Release:** in `finally` (success or exception), and only by the owner (`WHERE lock_owner = me`).
  One process can never release another process's valid lock.
* **Graceful shutdown:** on SIGTERM/SIGINT the worker sets a shutdown flag (`run_collector` refuses
  new scans), pauses the scheduler (no new jobs are dispatched) and calls `shutdown(wait=True)`, so
  a running scan (~15–20 s) finishes and releases its lock. Docker allows 60 s
  (`stop_grace_period`) before SIGKILL. A second signal is ignored.
* **Recovery on worker start:** locks with a stale heartbeat are released, and so are locks owned
  by a previous worker process on the same host (the worker has a fixed hostname,
  `dealhunter-worker`, and only one worker runs per deployment, so that process is certainly
  dead). Each recovery is logged (`stale_lock_recovered`, `startup_lock_recovery`). A restart after
  a SIGKILL therefore resumes immediately. Only a lock from a different host has to wait for the
  10-minute stale timeout.
* A killed scan leaves no partial data: the whole scan is one database transaction.
* **Health:** `/api/v1/sources`, `source-health` and the Sources page show `scan_lock` {locked,
  owner, acquired_at, age_seconds, heartbeat_at, heartbeat_age_seconds, stale} and `worker`
  {worker_scheduled, next_scheduled_scan, next_scan_overdue, next_scan_overdue_seconds,
  last_successful_scan}.
* **Overdue:** a graceful stop clears `next_run_at` ("not scheduled"). A hard-killed worker leaves
  it behind. Once it is more than `scan_schedule_overdue_seconds` (120) in the past, the source
  is reported **OVERDUE** and `healthy=false` (Sources and Overview pages show a red "WORKER
  OVERDUE" badge). The timestamp is kept for diagnosis. Detection latency: killed during a scan →
  ~2 min; killed between scans → up to one scan interval + 2 min (next_run_at still points to the
  planned scan).
* **Known limitation (accepted for v1):** a hard-killed *ad-hoc* scan (dashboard "Run now" or
  `scan-now` via `docker compose exec`) leaves its lock until the stale timeout (10 min), because
  only the worker's own predecessor lock is recovered instantly. One worker per deployment is
  assumed.

## Data flow for one scan

1. `worker` → `services.scan.run_collector("cardtrader")` takes the source scan lock (skipped if
   shutdown has begun or another process holds a valid lock).
2. `CardTraderCollector.sync_catalog` upserts cards/products for tracked sets (`config/sets.yaml`).
3. One `GET /marketplace/products?expansion_id=…&language=en` per set. Every listing is
   classified by `cardtrader_filters.classify_listings` (see "Which listings count" below).
   Valid prices are converted to NOK.
4. `compute_stats` over the valid listings → `PriceSnapshot` (low, cheapest-3/5/10 medians, broad
   and trimmed medians, valid and excluded counts, seller count, dispersion of the cheapest 10,
   expensive-tail flag).
5. The cheapest N **valid** listings per item become `Listing`s. Bulk with a cheapest-5 median under
   `min_fair_value_to_evaluate_nok` is priced but never evaluated, unless it is on the watchlist.
6. `services.evaluation.evaluate_listing`: build context (fair value, history, PSA refs, portfolio,
   watchlist), then `score_listing`, then `DealEvaluation`, then `policy.decide`, then maybe Telegram → `Alert`.
7. Unseen listings are marked `gone`. Today's `PriceDaily` aggregate is refreshed.
8. `CollectorRun` + `SourceStatus` are updated. After N consecutive failures, ONE health alert is
   sent, and a recovery message follows the next success.
9. Active FINN/manual listings are re-scored against the fresh fair values (no network).

## Which listings count (`collectors/cardtrader_filters.py`)

A CardTrader blueprint is one printing (its `version` carries rarity + `number/printed total`).
Within a blueprint, a listing counts toward prices only if it passes every filter. Each rejection
has a named reason, visible in `cardtrader-debug-card`:

- English only (API `language=en` plus a per-listing check)
- Mint/Near Mint only
- not graded: CardTrader's `graded` flag **or** PSA/BGS/CGC/"graded"/"slab" in the description
  (live data had PSA 9 slabs listed as "Near Mint")
- not reverse holo (`pokemon_reverse`: same blueprint, different product), not 1st edition,
  not signed, not altered
- no fake/foreign red flags in the description
- not on vacation, not a multi-card bundle
- **one listing per seller** (the seller's cheapest), so one seller's inventory cannot fill the
  cheapest-N window
- **no absurd/placeholder asks:** a listing priced more than `absurd_ask_multiple` (10×) above the
  lower-market cluster (the median of the cheapest half of valid listings, max 5) is excluded
  from all statistics, history, liquidity and fair value, but stays visible in
  `cardtrader-debug-card` ("absurd ask"). The rule is relative, never a fixed price. Live examples:
  10,000.64 EUR asks on a ~35 EUR Mew ex, and a ~109,000 NOK ask on a 221 NOK tin.

Prices always come from the per-expansion marketplace request. CardTrader's per-blueprint request
returns the same listings in another display currency, with a ~13% cross-currency markup (see
docs/SOURCES.md).

## Fair value (`pricing/fair_value.py`)

Fair value is what you can realistically **buy** for, not the average ask. Stale, overpriced
asks commonly sit 30–60% above the buyable market.

* ≥5 valid listings: `0.60 × cheapest-5 median + 0.25 × cheapest-10 median + 0.15 × own 30d
  median`, with weights renormalised over the parts that exist. Without history this is ~71/29
  cheapest-5/cheapest-10.
* 1–4 listings (thin market): cheapest-3 median, blended 60/40 with own history if available.
  Confidence is 0.3–0.6, which is below the alert threshold for 1–2 listings.
* The broad and trimmed medians **never set the price**. `market_has_expensive_tail` is flagged
  when the trimmed median is > 1.30 × the cheapest-5 median.
* One cheap listing cannot define fair value (it is at most one of five values in the median).
  `lowest_listing_outlier` is flagged when low < 0.70 × the cheapest-5 median.
* Own history (7/30/90 days) is built from daily **cheapest-5** medians, so the tail cannot creep
  back in through history.
* Falling market (30-day trend < −5%): capped at the current executable price.
* Confidence goes down for thin markets, a sharp price step after the 5 cheapest (cheapest-10 >
  1.3 × cheapest-5), dispersion among the cheapest 10, volatility, missing history and identity
  uncertainty. The low–high band widens accordingly.
* Every evaluation stores `fv_model`. When the model changes, old evaluations are re-scored on the
  next scan.
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

## Landed cost and seller regions (`pricing/landed_cost.py`)

Every listing stores `seller_country`, `seller_region`, item price, shipping, import buffer and
`landed_cost_nok = item + shipping + import buffer`.

* Region from the seller's ISO country (`region_countries` in `config/sources.yaml`): EEA, UK,
  Switzerland, US, Canada. Unknown or unlisted countries are "other".
* Shipping: `shipping_nok_by_region` for CardTrader (EEA 80, UK/CH 140, US/CA 250, other 300 NOK).
  FINN and web shops are Norwegian (region EEA) and use their own shipping.
* Import buffer: `import_buffer_by_region` (default 25% of item + 100 NOK for every non-EEA
  region, 0 for EEA). This is a deliberately conservative *uncertainty buffer*, not a tax
  calculation.
* **Discount, score and recommendation use the landed cost.** Fair value still uses item prices
  of valid listings from **all** regions.
* The "too good to be true" guard (`suspicious_discount`) compares the **item** price with fair
  value, because shipping dilutes the discount of cheap cards and would hide a suspicious listing.
* Alerts only for sellers in `deal_seller_regions` (default `[EEA]`). Other listings are still
  stored, priced and scored, but blocked with `seller_region_not_allowed`.

## CardTrader delivered cost (`pricing/landed_cost.py`)

Cheap item ≠ cheap delivered. Observed checkout (2026-10-01, Mew ex 205, direct seller):
$15.90 item + $16.42 shipping + $2.02 fees = $34.34. The old flat 80 NOK shipping made it a
41% "STRONG BUY".

* **Route** from the API's `user.can_sell_via_hub`: `direct` (the seller ships one parcel to
  Norway) or `zero` (CardTrader Zero: item → hub is free, then a separate final Zero shipment).
* **Single-card landed** = item + shipping + fees + import buffer. Each part has a **basis**:
  `exact` (seller-stated, or an observed checkout quote recorded with
  `shipping-quote add`) or `estimated` (config `cardtrader_costs`: direct EEA 170 NOK, Zero
  200 NOK, fees 20 NOK + 1%). `landed_cost_confidence` is 1.0 when everything is exact, 0.6 when
  estimated. Estimates are always labelled ("≈", "est.", "Shipping estimate — verify at
  checkout").
* **Guard:** with estimated shipping, STRONG BUY / STEAL need `estimated_shipping_margin` (5
  points) more landed discount than usual.
* The cheap listing itself stays **valid market data**: delivered cost affects the deal, never
  the fair value.
* **Seller baskets (groundwork):** one shipment can carry many cards. `basket_landed_cost` =
  Σ items + one shipment + order fees + import, with `shipping_per_card` = shipment / n.
  `basket-preview` and `GET /dashboard/baskets` compute it; nothing is purchased.

## Final live validation and market-data conflicts (`services/validation.py`)

The expansion-wide scan discovers candidates. **No alert is sent before a live validation**,
made at the moment of alerting (rate-limited to 0.5 req/s):

1. `marketplace/products?blueprint_id=…`: the candidate must still exist and be valid.
2. The same expansion request the scan uses (same currency view as history): filters → stats →
   fair value → score → alert policy all re-run on this fresh data.
3. Cross-check listing by listing. The endpoints present prices in different currencies with a
   uniform ~13% cross-currency markup per seller region (blueprint=USD/expansion=EUR: EEA
   sellers 1.13, US sellers 0.885). Absolute prices are never compared across endpoints. A
   conflict is raised when the endpoints disagree on the cheapest valid listings, when a
   listing's price deviates from its region's ratio, or when the fair value moved more than
   20% since the scan.

Outcomes: `ok` (decision re-made on fresh data), `stale` (candidate gone), `conflict` (stored as
`market_data_conflict` with full diagnostics), or `error` / `unvalidated`. None of the last
three ever alerts. Validation conflicts expire after 24 h and are re-checked. **Manual**
conflicts (`market-conflict add`) never expire. They exist for cases the API cannot show, e.g.
the CardTrader website listing offers the API does not return. A card with an open conflict never
alerts, and its fair value is never "corrected" by hand.

## Notification policy (`scoring/policy.py`)

`effective_level()` turns the raw score band into the **effective level**: the lower of the score
band and the level the landed-cost discount supports (15/22/30%). A STEAL score with an 18%
discount is therefore GOOD. The effective level is stored on every evaluation (`alert_level`, with
the cap reasons in `reason_json.effective`) whether or not alerts are enabled. It drives the
dashboard badge, the recommendation filter and the overview counts, and it *is* the Telegram
severity, because `decide()` uses the same function. `decide()` only adds the stateful part: hard
filters, cooldowns and the daily cap decide *whether* to notify, never the level.

An item priced more than 45% below fair value (`suspicious_discount`, measured on the item price)
is capped at STRONG BUY with a "verify listing" warning. In live data such listings were stale or
mispriced, so they must not bypass the daily cap as STEALs.

Listings from sellers outside `deal_seller_regions` never alert (`seller_region_not_allowed`).
Cooldowns apply per listing **and per card**, so two sellers at the same price produce one alert.
Only alerts from the current mode count: dry-run history never suppresses live alerts.

Hard filters:
seller region allowed, fair value ≥ 250 NOK (unless the item is on the high-priority watchlist), match confidence ≥ 0.90,
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

Raw `price_snapshots` are kept for 30 days, and `price_daily` aggregates are kept forever. Days are
**UTC days** (`db.base.utc_today`), matching the UTC timestamps. The containers run in
Europe/Oslo, and using the local date made scans between 00:00 and 02:00 aggregate the wrong day. The
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

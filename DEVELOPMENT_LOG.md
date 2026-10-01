# Development log

## 2026-10-01 — FINN discovery: user-driven capture, lots, FINN economics, safety labels

### Decision
- FINN's robots.txt prohibits crawling and "systematic or regular" automated use without written
  permission (quoted in docs/SOURCES.md). Automated search / saved-search discovery was therefore
  **not** built. `finn-scan-now` refuses with an explanation. Only robots.txt was fetched, and no
  FINN search page was ever requested. `finn.fetch_metadata` now defaults to false.
- Discovery is user-driven instead: a bookmarklet reads the ad in the user's own browser and opens
  `/capture` prefilled; the user confirms and saves. URL and CSV ingestion remain.

### Added
- `collectors/finn_text.py`: Norwegian shipping parser (exact / included / pickup / unknown) and
  lot extraction (quantity, card numbers, Pokémon, sets, grades, sealed products).
- `services/finn_analysis.py`: conservative lot identification (unique set+number match **and** the
  Pokémon named), and neutral safety labels.
- Migration 0007:
  - listing location, seller_type, published_at, pickup_required, capture_method, extracted,
    safety_flags
  - lot stated_quantity / extraction / image_analysis
  - lot_item origin
- Lot alert gate: unknown item count or < 70 % identified → no alert. The lot fair-value confidence
  scales with coverage.
- API: `POST /api/v1/finn/capture`, `GET /dashboard/finn`.
  CLI: `finn-source-health`, `finn-debug-listing`, `finn-scan-now`.
- Dashboard:
  - `/capture` page with the bookmarklet
  - FINN panels on Overview and Sources
  - added-age, pickup and lot badges on FINN deals
  - capture method, pickup and safety checks on Listings

### Verified
- pytest 227 passed, ruff clean. Web: tsc, lint, 7 tests and build clean.
- Docker: migration 0006 → 0007 applied. `/capture` 200, `dashboard/finn` ok.
- No `finn.no` request appears in the API or worker logs.

## 2026-10-01 — CardTrader delivered cost (cheap item ≠ cheap delivered)

### Finding (manual checkout)
- Mew ex 205/165, direct seller PokeBilly (BE): $15.90 item + $16.42 shipping to Norway + $2.02
  fees = **$34.34**. CardTrader Zero alternative: $34.94 item + $2.15 fees (+ the final Zero
  shipment separately). Our flat 80 NOK "EEA shipping" priced the Mew at 224 NOK landed and
  produced the STRONG BUY. The cheap listing is real and buyable; the problem was delivered cost.
- The manual `market_data_conflict` for Mew is resolved (note kept). The website/API listing
  difference stays documented in docs/SOURCES.md.

### Changes
- CardTrader landed cost by route (direct / CardTrader Zero via `can_sell_via_hub`), estimated
  fees, an `exact` / `estimated` basis per component, and landed-cost confidence (migration
  0006). Seller checkout quotes (`seller_shipping_quotes`, `shipping-quote add|list`) make
  shipping exact.
- Level guard: estimated shipping needs +5 points of landed discount for STRONG BUY / STEAL.
- Seller-basket groundwork: `basket_landed_cost`, `basket-preview`, `GET /dashboard/baskets`.
- Dashboard: shipping/fees labelled "quote" vs "est.", "≈" landed cost, a "Shipping estimate —
  verify at checkout" note with confidence and route. Telegram labels estimates too.

### Result (live)
- Mew (exact quote): 144 + 158 + 19 = 321 NOK landed, 15.7% → GOOD. It alerts as GOOD via the
  high-priority-missing rule. Without the quote (estimated): 335 NOK, 11.9% → WATCH.
- Eevee 188 (direct, estimated): 1,069 NOK landed, 9.4% → WATCH. Gengar ex 193 (Zero,
  estimated): 745 NOK, −2.1% → WATCH. Neither alerts any more.

## 2026-10-01 — Market-data input: placeholder asks, final live validation, conflicts

### Investigation (Mew ex 205/165, blueprint 258698)
- The user saw several EN NM offers at ~$15.90 on the website (CT Min $15.90, CT Market $20.14).
  Our fair value was 34.91 EUR.
- Both API endpoints return the **same** listings (EN ids 46/47 shared; all languages 93/95; no
  truncation). There is no hidden native-price field (`price_cents` == `price`), the blueprint
  is the same, and filtering is not the cause (the raw rows contain no other EN NM ask under ~34).
- The endpoints differ only by a symmetric ~13% cross-currency presentation (EEA ×1.13 in the
  USD view, US ×0.885).
- **Neither endpoint contains the ~$15.90 offers.** The website itself is behind bot protection
  (HTTP 503 to a scripted request, not bypassed). Mew is flagged with a manual
  `market_data_conflict`, and its fair value is left as the API data supports.
- 3 placeholder asks at 10,000.64 EUR were counted as valid listings. They did not move the
  cheapest-5 / fair value, but did inflate the broad/trimmed medians and listing counts.

### Changes
- Relative absurd-ask exclusion (`absurd_ask_multiple: 10` × the lower-market cluster). 5×
  was tried first: an audit showed 2,680 ordinary bulk exclusions (0.10 vs 0.60 EUR), so it was
  raised to "wildly above". It also fixes the thin-market placeholder case (Mini Tin fair
  value 54,627 → 221 NOK).
- Final live validation of every alert candidate (exact blueprint + same-moment expansion data,
  per-region cross-check, fresh fair value/score/policy). `market_data_conflicts` table
  (migration 0005), automatic + manual (`market-conflict add|list|resolve`), and
  `alert-preview --validate`.
- Price history reset and rebuilt (one day) without placeholder asks; model `executable-v7`.

### Result
- `alert-preview`: Mew ex blocked (market_data_conflict, manual). Eevee 188 and Gengar ex 193
  validated `ok` and still alert as GOOD. Gastly 177 is consistent across endpoints (not a
  candidate).

## 2026-10-01 — Advanced collector dashboard

### Built
- **Read models** (`services/dashboard.py`, `/api/v1/dashboard/*`, read-only): overview,
  deals + deal detail, portfolio (+ holdings), binder (premium/regular), sealed, grading,
  watchlist, market + per-card series, alerts (sent + held back), system. One call per page.
  Nothing is fabricated: history/PSA/prices that don't exist are `null` / `ready: false`.
- **Dashboard** (Next.js, dark-first): new shell with grouped navigation (Overview · Trading ·
  Collection · Market · System), a phone bottom tab bar + drawer, and a live scanner status pill.
  Shared UI kit (`components/ui.tsx`): KPI cards, effective-level badges, responsive DataTable
  (cards on phones), card thumbnails (CardTrader previews), empty/"history is being collected"
  states. One validated chart palette (`lib/chart.ts`).
- Pages: Overview, Deals (+ detail sheet), Watchlist, Portfolio, GOD Binder (216-pocket map),
  Collection (360), Sealed, Grading, Market, Alerts, Listings (+ match review), Sources,
  System, Settings. `/prices` → `/market`, `/review` → `/listings?tab=review`,
  `/health` → `/system` redirect.
- Config: `binders.yaml` `capacity_slots` (216 / 360). Grading status `at_grader` added.
  The prod overlay mounts `./backups` read-only into the API for backup status.
- Tests: backend 178 (dashboard read models incl. no-fabrication rules), frontend `npm test`
  (formatting: NOK, %, dates, relative UTC times).

### Bugs found and fixed
- **Daily price history was empty despite 20k snapshots.** Containers run in Europe/Oslo;
  `aggregate_day(date.today())` used the local date while snapshots are UTC, so scans between
  00:00 and 02:00 local built nothing, and the 7/30/90-day windows were shifted by a day. Now
  UTC days everywhere in price history (`utc_today`), with a regression test that fails on the
  old code at any hour.
- `/system` `overall_ok` treated a stopped worker as operational → now requires a scheduled scan.

### Found, not changed (fair-value logic is frozen)
- **Thin market with a placeholder ask:** with exactly 2 valid listings, the cheapest-3 median
  is their average. Live example: Paldea Friends Mini Tins with asks of 221 NOK and ~109,000 NOK
  → fair value 54,627 NOK (confidence 0.36). No alert is possible (confidence < 0.5 → IGNORE),
  and the dashboard's "strongest discounts" now only shows fair values with confidence ≥ 0.5.
  Proposed fix for a future pricing change: with < 3 listings, ignore asks > 3× the lowest, or
  use the lower ask plus a wide band.

## 2026-10-01 — Scan-lock ownership, graceful worker shutdown, stale-lock recovery, overdue detection

### Problem
The worker stopped with `shutdown(wait=False)`. A scan running at SIGTERM was abandoned with
its lock set, and a lock only expired after 45 minutes. So a restart, deploy or reboot during a
scan silently paused all scanning for up to 45 minutes (seen in practice on 2026-10-01). Any
process could also clear any lock.

### Changes
- `services/locks.py`: lock owner (`role@host#pid-instance`), acquired_at, heartbeat thread
  (60 s); staleness measured from the last heartbeat; atomic acquire; owner-only release in
  `finally`; start-up recovery of stale locks and of the same-host predecessor's lock.
- Stale timeout 45 min → **10 min**, configurable: `scheduler.scan_lock_stale_minutes`, with
  `scan_lock_heartbeat_seconds` validated to be < half of it.
- Worker: SIGTERM/SIGINT → shutdown flag + pause + `shutdown(wait=True)`; no new scans once
  shutdown has begun; next scheduled scan recorded after each job and every minute.
- Docker: worker and api `stop_grace_period: 60s`; worker `stop_signal: SIGTERM` and a fixed
  `hostname: dealhunter-worker` (container IDs change on recreate, which would defeat predecessor
  recovery).
- Migration `0004`: `source_status.lock_owner`, `lock_heartbeat_at`, `next_run_at`.
- Health: `scan_lock` {locked, owner, acquired_at, age_seconds, heartbeat_at,
  heartbeat_age_seconds, stale}, `next_scheduled_scan` and `worker_scheduled` in
  `/api/v1/sources`, `source-health` and the Sources page.
- **Overdue detection:** `scan_schedule_overdue_seconds: 120`. `worker` health block
  {worker_scheduled, next_scheduled_scan, next_scan_overdue, next_scan_overdue_seconds,
  last_successful_scan}; overdue ⇒ `healthy=false` and a red "WORKER OVERDUE" badge on the Sources
  and Overview pages. A graceful stop clears the schedule. A stale timestamp from a hard kill turns
  overdue, and the timestamp is kept for diagnosis.
- **Database clock:** `db/clock.py::db_now` (Postgres `clock_timestamp()`, SQLite `strftime`). It is
  authoritative for lock acquire, heartbeat, stale detection, start-up recovery, health ages and
  the stored next-run time.
- Tests: 164 (acquire/release, release on exception, graceful shutdown waits and blocks new jobs,
  fresh lock respected, stale >10 min reclaimed, live heartbeat never stale, owner-only
  release/heartbeat, restart after interrupted scan, recovery leaves foreign/own locks alone,
  config validation, health API, DB-time stale detection, ±3 h app clock skew, heartbeat vs
  reclaim, next run stored in DB time, overdue: future / inside grace / past grace / no timestamp,
  graceful stop clears / hard-kill goes overdue / restart clears).

### Verified live (Docker, real CardTrader scans)
- SIGTERM mid-scan: `scheduler_stopping` → scan finished (`collector_run_ok`, success) →
  `scheduler_stopped`. Restart took 11 s; the lock was free immediately; the new worker scanned
  on schedule.
- SIGKILL mid-scan: the lock was left behind; on `start` the worker logged `stale_lock_recovered`
  (previous worker process on this host) and scanned on schedule. No dead period. The killed
  scan left no partial data (single transaction).
- A foreign lock 11 min old was shown as stale and reclaimed by the next scan. A fresh foreign
  lock was respected.
- Overdue: after SIGKILL (with next_run_at moved 5 min into the past to simulate elapsed time),
  `source-health` showed `[BAD] … worker: OVERDUE … 301s ago`, the API reported `healthy=false`,
  `next_scan_overdue=true`, and the Sources page showed WORKER OVERDUE. On `docker compose start
  worker`, the lock was recovered and OVERDUE cleared within 5 s; the scan ran on schedule
  (success) and the next scan was set 30 min ahead.

## 2026-10-01 — Seller regions and landed cost (model `executable-v6-landed`)

### Changes
- `pricing/landed_cost.py`: seller country → region (EEA / UK / Switzerland / US / Canada / other),
  `landed = item + shipping by region + import buffer by region`. The flat 60 NOK CardTrader
  shipping estimate is replaced by `shipping_nok_by_region` (EEA 80, UK/CH 140, US/CA 250,
  other 300). The import buffer is 25% of item + 100 NOK for non-EEA, 0 for EEA. It is an
  uncertainty buffer, not a tax calculation.
- Discount, score and recommendation use the landed cost. Fair value keeps valid listings from
  all regions.
- Alerts only for `deal_seller_regions` (default `[EEA]`). Others are blocked with
  `seller_region_not_allowed`, but still stored, priced and scored.
- Effective level: the dashboard badge shows the level after the discount cap and the
  suspicious-price guard (`policy.effective_level`, stored as `deal_evaluations.alert_level` with the
  cap reasons), not the raw score band. The raw score and band stay visible, and the expanded row
  shows band → level → caps. Telegram severity already used this logic; it now calls the same
  function, so badge and alert cannot diverge. The recommendation filter and overview counts use
  the effective level.
- Migration `0003`: listings get `seller_country`, `seller_region`, `import_buffer_nok`,
  `landed_cost_nok`; deal evaluations get `alert_level`. FINN and web shops are Norwegian sellers (EEA) with their own shipping.
- The suspicious-discount guard now compares the **item** price with fair value. With the higher
  EEA shipping estimate, the stale 13 EUR Mew ex listing's landed discount fell to 41%, which
  silently lifted the cap. Its item price is 62% under fair value.
- CLI: `cardtrader-debug-card` shows region, item/shipping/import/landed cost, discount and deal
  eligibility per listing. `alert-preview` and `evaluate-listing` show the cost breakdown.
- Dashboard: seller country and region, landed cost with breakdown, region filter, landed-cost
  price filters, and a cost breakdown in the expanded row.
- YAML gotcha: unquoted `NO` (Norway) parses as `false`. Country codes are quoted, and pydantic
  rejects the config loudly if this ever regresses.
- Tests: 139 (effective-level caps and badge/Telegram consistency, EEA/UK/US/unknown country, outside-region block, fair value keeps all regions,
  landed-cost discount, upsert storage, end-to-end block persisted, item-price suspicious guard).

### Effect on alerts (live data, alert-preview)
Same 3 alerts, all EEA sellers, with smaller discounts because EEA shipping is now 80 NOK
instead of 60:
- Mew ex 205 (BE): 144 + 80 = 224 NOK vs fair value 381 → 41.2% landed, 62% item → STRONG BUY
  (capped) + verify warning
- Eevee 188 (IT): 870 + 80 = 950 vs 1,179 → 19.4% → GOOD
- Gengar ex 193 (FI): 519 + 80 = 599 vs 729 → 17.8% → GOOD

Charizard ex 199 stays blocked (11.4%). Non-EEA: 270 evaluated listings, 0 GOOD+. Two non-EEA
listings looked like 28–32% deals on sticker price (GB Perrin 220, CH 151 Booster Bundle); landed
cost drops them to 8% / 5.5% (IGNORE).

## 2026-10-01 — Fair-value audit against live CardTrader data (model `executable-v3`)

### Audit findings (live Temporal Forces data, 81,754 English listings across 5 sets)
- The old fair value (60% trimmed median + 40% cheapest-5) let stale expensive asks dominate.
  Gastly 177 was ~109.5 EUR, while only 3 NM copies exist below 81 EUR.
- Card identity was correct (one blueprint per printing), but live card numbers were stored
  without the printed total ("177"), which capped FINN title matches at 0.85 (never auto).
- Not filtered before: reverse holos (4,979 of 15,708 English TEF rows share a blueprint with the
  normal card), signed/altered copies, 1st edition, graded slabs described in text, multiple
  listings from one seller.
- The first dry run in mock mode had linked the seeded watchlist cards to mock blueprints, so live
  cards were created as duplicates.
- The per-blueprint and per-expansion endpoints return the same listings in different display
  currencies with a ~13% cross-currency markup (see docs/SOURCES.md).
- Bugs found along the way: (1) the notification decision was never persisted (in-place JSON
  mutation after flush), (2) dry-run alerts counted toward live cooldowns/daily cap, (3) two
  sellers at the same price produced two alerts for one card, (4) the Docker image installed an
  empty stub `app` package into site-packages, (5) `docker compose build api` built nothing
  (only `migrate` had a build section), (6) the seed rarity for Gastly 177 was wrong (it is an
  Illustration Rare).

### Changes
- `collectors/cardtrader_filters.py`: explicit per-listing exclusion reasons + one listing per seller.
- New fair-value model (executable market, tail and outlier flags, thin-market handling);
  history now built from daily cheapest-5 medians. Migration `0002` adds
  cheapest-3/10 medians, excluded count and the tail flag.
- Blueprint `version` parsing → `number/printed total` + rarity; CardTrader is authoritative.
- New CLI: `cardtrader-debug-card`, `alert-preview`, `purge-mock-data`, `reset-price-history`;
  `cardtrader-check` shows valid/all counts, cheapest-N and fair values.
- Policy: `suspicious_discount` (≥45% → capped at STRONG BUY + verify warning), per-card
  cooldown, mode-separated alert state, clearer block reasons. Evaluations carry `fv_model` and
  are re-scored when it changes.
- Dashboard price chart shows the cheapest-5 (buyable) line and the fair-value flags.
- Tests: 115 (new: tight market, overpriced tail, under/over-priced outlier, 1–2 listings, thin
  market with history, volatile market, formula weights, real Gastly shape, filters, version
  parsing, mock purge, persistence, dry-run separation, per-card cooldown, suspicious cap).

### Live results (TEF, EUR, no own history yet)
| Card | low | c5 | c10 | trimmed | old formula, same data | new FV | conf | flags |
|---|---|---|---|---|---|---|---|---|
| Gastly 177/162 IR | 70.64 | 80.62 | 121.37 | 128.82 | 109.54 | 92.61 | 0.77 | expensive tail |
| Raging Bolt ex 208/162 SIR | 56.63 | 60.64 | 75.13 | 79.64 | 72.04 | 64.90 | 0.90 | expensive tail |
| Gengar ex 193/162 | 47.64 | 66.67 | 67.47 | 68.26 | 67.62 | 66.91 | 0.90 | – |
| Morty's Conviction 211/162 SIR | 55.53 | 60.64 | 74.18 | 67.29 | 64.63 | 64.62 | 0.90 | – |
| Gouging Fire ex 204/162 SIR | 34.47 | 45.64 | 64.32 | 64.32 | 56.85 | 51.13 | 0.77 | expensive tail |

Alert impact: the old model produced 6 dry-run alerts on the first live scan (3× Gastly 177 at
7–18% real discount, 2× the same Charizard at 11.8%, 1 uncapped STEAL on a stale 13 EUR Mew ex
listing). `alert-preview` under the new model: 3 real alerts (Mew ex capped at STRONG BUY with
a verify warning, Eevee 188 at 21%, Gengar ex 193 at 21%), plus one from my own FINN test listing,
which has since been removed. The Charizards are held back.

## 2026-09-30 — v0.1.0 (Phase 1 MVP)

### Built
- Monorepo: `apps/api` (FastAPI + worker + CLI), `apps/web` (Next.js dashboard), `config/`,
  `infra/`, `scripts/`, `docs/`.
- Data model (16 tables) + Alembic migration `0001`.
- CardTrader API v2 client (retries, backoff, rate limiting) + deterministic mock client.
  Catalogue sync, per-set marketplace scan, NM/EN filtering, price stats, snapshots.
- FX from Frankfurter (ECB), cached daily, with fallback rates.
- Fair-value estimator, history aggregates (7/30/90/all-time, trend, volatility), retention.
- Matching engine (numbers, sets, aliases, printed-total inference, EN/NO product keywords, lots,
  language, grades, fuzzy names, ambiguity guard) + manual review API/screen.
- Scoring engine + notification policy (bands, discount-capped severity, hard filters, cooldown,
  daily cap, STEAL exemption, GOOD special rules).
- Portfolio (binders, valuation, graded values, snapshots, 30-day change), watchlist, manual PSA
  references + CSV import, grading economics (PSA 9 vs 10 flags).
- Sealed analysis (per-pack, loose-pack equivalence, sealed premium, rip score vs sealed-hold
  score, explicitly no EV claims).
- Lots: manual item breakdown, image upload, conservative valuation. `LotImageAnalyzer` stub.
- FINN manual ingestion (URL/CSV/JSON, robots-gated single-page metadata read).
- Shopify store adapter (opt-in, robots-enforced).
- Telegram notifier (HTML, inline "Open listing" button, dry-run), health alerts (one alert per
  outage + recovery message), optional WATCH digest.
- APScheduler worker (heartbeat healthcheck, CardTrader every 30 min, FX daily, maintenance,
  portfolio snapshot).
- CLI: scan-now, add-listing, add-card, add-portfolio-item, add-graded, test-telegram,
  backfill-prices, sync-catalog, cardtrader-check, source-health, evaluate-listing,
  seed-watchlist, import-listings, maintenance, setup.
- Docker Compose (postgres, migrate, api, worker, web) + prod overlay (log rotation, no API port,
  backup container with 7 daily + 4 weekly). Backup/restore scripts.
- Tests: 78 pytest tests (scoring scenarios, fair value, FX/normalisation, duplicates, cooldown,
  thresholds, portfolio modifiers, matching, FINN parsing, URL validation, redaction, CardTrader
  client, end-to-end pipeline, health alerting, API).

### Verified
- `pytest`: 78 passed. `ruff`: clean. `npm run build` + `npm run lint`: clean.
- `docker compose up -d --build`: all services healthy, migration applied on Postgres, `/ready` ok.
- Worker started the scheduler, ran a mock CardTrader scan and produced a (dry-run) GOOD alert.
- Sample FINN listing evaluation, Telegram dry-run, all dashboard pages load with data.
- Backup script: dump + rotation (7 kept) verified against the running Postgres.

### Fixed before first commit
- Test isolation: once a local `.env` existed, pydantic-settings loaded its `API_KEY` into the
  test run (3 API tests failed with 401). `tests/conftest.py` now sets secrets to empty env vars,
  which take precedence over `.env`, so tests never depend on local secrets.

### Known limitations
- Live CardTrader not verified yet (no token during development). Mock mode is used.
- CardTrader exposes current asks, not sold prices. History is only as old as the install.
- Deals page source filter lists cardtrader/finn/manual. Store sources are not selectable yet.
- Settings are read-only in the UI (edit `config/*.yaml`).

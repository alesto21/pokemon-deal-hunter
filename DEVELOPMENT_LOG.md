# Development log

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

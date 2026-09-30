# Development log

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

# Development log

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

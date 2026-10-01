# Sources: what is supported, and what isn't

| Source | Status | Access method | Notes |
|---|---|---|---|
| CardTrader | ✅ v1, primary pricing + listings | Official API v2, Bearer token | 1 request per tracked set per scan. Limits: 200 req/10 s overall, 10 req/s on marketplace. We default to ≤2 req/s. |
| FINN.no | ✅ user-driven only (crawling prohibited) | Browser capture / pasted URL / CSV | See below. |
| Norwegian web shops | ⚙️ v1 framework, opt-in | Public Shopify `products.json` | Disabled by default. `robots.txt` enforced. Add shops in `config/sources.yaml`. |
| Frankfurter (ECB FX) | ✅ | Free public API, no key | Refreshed at most once a day and cached in the DB. Fallback rates in `config/currencies.yaml`. |
| Telegram | ✅ | Bot API | Dry-run when not configured. |
| eBay Browse API | ⏳ phase 2 | Official API (free developer account) | Not implemented. |
| PSA / graded prices | ✅ manual | CSV/API/CLI entry | No paid API. References carry source + confidence + date. |

## CardTrader

* Token: CardTrader → your profile → **Settings → API** (see https://www.cardtrader.com/docs/api).
  Put it in `CARDTRADER_API_TOKEN`.
* Without a token the app runs in **MOCK mode**: deterministic sample data for a handful of
  cards/products. Mock prices are illustrative, NOT real market prices. `/ready`, the Settings page
  and the logs all say `mock`.
* Endpoints used: `/info`, `/games`, `/categories`, `/expansions`, `/blueprints/export`,
  `/marketplace/products`. Nothing undocumented.
* The marketplace endpoint returns the currently active listings per item. On Temporal Forces we
  saw up to 185 rows for one card and 81,754 English rows across 5 sets. Whether it is
  exhaustive for very liquid cards is not documented. Our stats describe the **current asking
  market**, not completed sales. CardTrader does not expose sold prices. Our own history (daily
  aggregates of the cheapest-5 median) builds up from the day you start.
* Tracked sets: `cardtrader_track: true` in `config/sets.yaml`. The collector matches by set code
  or name. If CardTrader uses a different code, set `cardtrader_expansion:` for that set. Run
  `python -m app.cli cardtrader-check --set-code XXX` to see what matched.
* **Currency quirk (observed 2026-10-01):** `/marketplace/products?expansion_id=` returned every
  listing in EUR, while `?blueprint_id=` returned the same listing IDs in USD. Native-currency
  sellers matched (EU sellers in EUR, US sellers in USD), but the cross-currency figures included a
  ~13% markup in both directions (e.g. a BE listing showed 70.64 EUR and 90.64 USD, and a US
  listing 115.67 EUR and 116.23 USD). The collector and the debug command both use the
  per-expansion request only, and warn if a response ever mixes currencies. US/CA listings are
  therefore priced ~13% above their native asks, which only makes the estimate more conservative.
  They rarely sit in the cheapest 5 for EU-available cards.
* **Endpoint presentation (re-measured 2026-10-01, Mew ex 205/165):** both endpoints return
  the same listings (46/47 EN ids overlap; all languages 93/95 — no pagination or truncation).
  Their prices differ only by a symmetric ~13% cross-currency markup: EEA sellers ×1.13 in the
  USD view, US sellers ×0.885 (i.e. +13% in the EUR view). `price_cents` always equals `price`.
* **Website vs API:** the CardTrader website showed several English NM Mew ex 205/165 offers at
  ~$15.90 (CT Min $15.90, CT Market $20.14). Neither API endpoint returns them for our account:
  after one 13.19 EUR listing, the next English NM ask is ~34 EUR / $34. A scripted request
  to the website got HTTP 503 (bot protection), and we do not bypass it. The card is flagged
  with a manual `market_data_conflict` and never alerts until resolved. A manual checkout later
  showed that the cheap API listing (13.19 EUR ≈ $15.90) is real and buyable, but it costs $34.34
  delivered ($16.42 shipping + $2.02 fees). So the conflict was resolved (note kept), and the
  problem was fixed in the delivered-cost model below. If you see such a gap for another card, run
  `python -m app.cli market-conflict add --blueprint <id> --reason "…"`.
* Valid-listing filters and exclusion reasons: see ARCHITECTURE.md → "Which listings count", or run
  `python -m app.cli cardtrader-debug-card --set-code TEF --card-number 177`.
* **Delivered cost:** landed = item + shipping + CardTrader fees + import buffer. A cheap item is
  not a cheap delivered card.
  - **Shipping** is *exact* only for a checkout quote you observed and recorded
    (`python -m app.cli shipping-quote add --seller … --shipping … --fees … --currency …`).
    Otherwise it is an *estimate* from `cardtrader_costs` in `config/sources.yaml`: direct seller
    to Norway by region (EEA 170 NOK), or the CardTrader Zero route (200 NOK final shipment).
  - **Fees** are estimated at 20 NOK + 1%.
  - **Labelling:** estimates show "≈" / "est." in the dashboard and "shipping estimate — verify at
    checkout" in alerts.
  - **Alert margin:** STRONG BUY / STEAL need an extra 5 pp margin when shipping is estimated.
  - **Real costs vary** by seller, parcel weight, tracking and basket size, so always verify at
    checkout.
* **Seller baskets:** one shipment can carry many cards from the same seller, which spreads
  shipping and fees. `python -m app.cli basket-preview <listing_id> --cards 1,2,5,10` and
  `GET /dashboard/baskets` show the per-card landed cost (calculation only; nothing is bought).
  Alerts still price a single-card purchase.
* The seller country comes from CardTrader's `user.country_code`. Alerts are limited to
  `deal_seller_regions` (default EEA). All regions still count toward fair value. Import buffers
  are uncertainty allowances, not tax calculations.

## FINN.no

**Automated discovery is not built, on purpose.** FINN's `robots.txt` (checked 2026-10-01) starts:

> Crawling FINN.no is prohibited unless you have written permission. … Bruk av automatiserte
> tjenester (roboter, spidere, indeksering m.m.) samt andre fremgangsmåter for systematisk eller
> regelmessig bruk er ikke tillatt uten eksplisitt samtykke fra FINN.no.

Saved-search polling, search-page parsing and scheduled scans would all be "systematic or regular
use", so `finn-scan-now` refuses and explains why (exit code 2). If you obtain written permission,
that is the point to revisit it. Deal Hunter makes **no** requests to FINN by default
(`finn.fetch_metadata: false`).

Discovery is user-driven instead. You browse FINN as normal, and Deal Hunter does the analysis:
- **Browser capture** (`/capture`, also linked from Listings and Sources). A bookmarklet runs in
  *your* browser on the ad you are viewing. It reads the page's public meta tags (`og:*`, product
  price, JSON-LD) and opens `/capture#<data>`. The fragment never leaves the browser. You check
  the prefilled form, add location/seller/shipping, and save (`POST /api/v1/finn/capture`).
- **Pasted URL:** `python -m app.cli add-listing <finn-url> --title … --price … [--shipping …]`.
- **CSV/JSON import:** `python -m app.cli import-listings file.csv`
  (`docs/examples/finn_listings.csv`).

Every listing records its `capture_method` (`capture` / `manual` / `csv`).

What happens on ingest (deterministic, no network):
- **Shipping:** a value you type is *exact*. Otherwise it is read from the text:
  - "frakt 79 kr" / "99,- i frakt" → exact
  - "fri frakt" / "frakt inkludert" → included
  - "kun henting" / "må hentes" → pickup (landed = item price; a "pickup required" warning is
    shown, travel cost not included)

  Otherwise it is *estimated* at `finn.estimated_shipping_nok` (99). Estimated shipping is labelled
  "est." everywhere, and needs a +5 pp margin to reach STRONG BUY / STEAL.
- **Matching:** the normal catalogue matcher. Ambiguous matches go to the review queue.
- **Lot detection:** lot words (samling, perm, bulk, binder …), stated quantity ("150 kort"),
  several card numbers, mixed sealed products, many Pokémon, or several PSA grades.
  - A lot is never forced into a single-card match.
  - Extracted Pokémon, sets, card numbers, grades and sealed products are stored on the lot.
  - A card is *identified* only when set + number match exactly one catalogue card **and** that
    Pokémon is named in the text. Everything else is unidentified and valued at 0.
  - Lot alerts need a known item count and ≥ 70 % of items identified (`lot_min_coverage`).
- **Safety labels:** neutral "verify" labels, never accusations, shown on the deal and in alerts:
  - very short description
  - no photos captured
  - very new listing
  - duplicate-looking listing
  - repeated seller (≥ 5 active)
  - business seller
- **Duplicates:** the same FINN item id updates the existing row (price-change history kept).
  Removed ads go `gone` via maintenance; you can also mark them sold/ignored.

CLI:
- `finn-source-health`: counts and the discovery status
- `finn-debug-listing <id> [--reanalyse]`: shipping parse, lot extraction, flags and score
- `finn-scan-now`: refuses and explains why (exit code 2)

`finn-search-list` / `finn-search-add` were not added, since saved-search polling is not
permitted. Re-scoring: active FINN listings are re-scored after each CardTrader scan, with no FINN
requests.

Not supported, by design: searching, crawling or polling FINN; logging in; any circumvention of
rate limits, CAPTCHAs or anti-bot measures; detecting that a FINN listing sold.

## Web shops (Shopify adapter)

Many small Norwegian TCG shops run on Shopify, which publishes
`/collections/<handle>/products.json`. The adapter:
- is off by default (`stores.enabled: false`, and per shop `enabled: false`)
- checks `robots.txt` before every run and fails the run if disallowed
- rate-limits to 0.5 req/s and reads at most 4 pages
- respects each shop's terms. Check them before enabling a shop.

Other store platforms: implement `StoreAdapter.fetch()` in `collectors/stores.py` and register it
in `ADAPTERS`.

# Sources: what is supported, and what isn't

| Source | Status | Access method | Notes |
|---|---|---|---|
| CardTrader | ✅ v1, primary pricing + listings | Official API v2, Bearer token | 1 request per tracked set per scan. Limits: 200 req/10 s overall, 10 req/s on marketplace. We default to ≤2 req/s. |
| FINN.no | ✅ v1, manual only | URLs you paste / CSV / JSON | See below. |
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
* The marketplace endpoint returns the cheapest listings per item (not every listing ever). Our
  stats therefore describe the **current asking market**, not completed sales. CardTrader does not
  expose sold prices. Our own history (daily aggregates) builds up from the day you start.
* Tracked sets: `cardtrader_track: true` in `config/sets.yaml`. The collector matches by set code
  or name. If CardTrader uses a different code, set `cardtrader_expansion:` for that set. Run
  `python -m app.cli cardtrader-check --set-code XXX` to see what matched.
* Shipping from CardTrader sellers varies by seller and country. We add a flat configurable
  estimate (`estimated_shipping_nok`, default 60 NOK).

## FINN.no

FINN does not offer a marketplace-wide API to private users. This project does **not** pretend
otherwise, and it does **not** scrape search results.

Supported:
- `python -m app.cli add-listing <finn-url> [--title … --price … --shipping …]`
- Dashboard → Deals → **Add FINN listing**, or CSV/JSON import (`docs/examples/finn_listings.csv`)
- Optional metadata read: when you add a URL without title/price, the app makes **one** normal GET
  of that single page, and only if `robots.txt` allows it for our user agent. It reads only the
  page's public metadata (`og:title`, price meta / JSON-LD, image). If that fails, you are asked to
  supply title and price. Disable it with `finn.fetch_metadata: false`.
- Re-scoring: active FINN listings are re-scored after each CardTrader scan (no FINN requests).

Not supported, by design:
- Searching or crawling FINN, polling saved searches, logging in, or any circumvention of
  rate limits, CAPTCHAs or anti-bot measures.
- Detecting that a FINN listing sold. Mark it `sold`/`ignored` in the dashboard, or it goes
  `gone` after 14 days.

Phase-2 hook: `collectors/finn.py::ListingDiscovery`. Something that yields listing URLs from a
permitted channel (for example, parsing FINN saved-search notification e-mails you receive) can
feed `ingest_url` without touching FINN's search.

## Web shops (Shopify adapter)

Many small Norwegian TCG shops run on Shopify, which publishes
`/collections/<handle>/products.json`. The adapter:
- is off by default (`stores.enabled: false`, and per shop `enabled: false`)
- checks `robots.txt` before every run and fails the run if disallowed
- rate-limits to 0.5 req/s and reads at most 4 pages
- respects each shop's terms. Check them before enabling a shop.

Other store platforms: implement `StoreAdapter.fetch()` in `collectors/stores.py` and register it
in `ADAPTERS`.

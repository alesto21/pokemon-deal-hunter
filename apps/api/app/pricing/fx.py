"""Currency normalisation. Rates from the free ECB-backed Frankfurter API, cached daily in the DB."""

from __future__ import annotations

from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings, get_user_config
from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.models import ExchangeRate

log = get_logger(__name__)


class FxRates:
    """NOK-per-unit rate table with conversion helpers."""

    def __init__(self, nok_per_unit: dict[str, float], as_of: date | None = None, fallback: bool = False):
        self.nok_per_unit = {k.upper(): v for k, v in nok_per_unit.items()}
        self.nok_per_unit["NOK"] = 1.0
        self.as_of = as_of
        self.fallback = fallback

    def to_nok(self, amount: float, currency: str) -> float:
        currency = currency.upper()
        if currency not in self.nok_per_unit:
            raise ValueError(f"No exchange rate for {currency}")
        return round(amount * self.nok_per_unit[currency], 2)

    def convert(self, amount: float, src: str, dst: str) -> float:
        nok = self.to_nok(amount, src)
        return round(nok / self.nok_per_unit[dst.upper()], 2)


def refresh_rates(session: Session, client: httpx.Client | None = None, force: bool = False) -> FxRates:
    """Fetch today's rates at most once per day."""
    today = date.today()
    if not force:
        existing = session.scalars(select(ExchangeRate).where(ExchangeRate.day == today)).all()
        if existing:
            return FxRates({r.currency: r.nok_per_unit for r in existing}, today)
    cfg = get_user_config().currencies
    wanted = sorted(set(cfg.fallback_rates_nok) | set(cfg.display_currencies) - {"NOK"})
    own_client = client is None
    client = client or httpx.Client(timeout=15, headers={"User-Agent": get_settings().http_user_agent})
    try:
        resp = client.get(cfg.fx_provider_url, params={"base": "NOK", "symbols": ",".join(wanted)})
        resp.raise_for_status()
        data = resp.json()
    finally:
        if own_client:
            client.close()
    rates: dict[str, float] = {}
    for cur, per_nok in data.get("rates", {}).items():
        if per_nok:
            rates[cur] = round(1.0 / float(per_nok), 6)
    for cur, value in rates.items():
        row = session.scalar(select(ExchangeRate).where(ExchangeRate.day == today, ExchangeRate.currency == cur))
        if row:
            row.nok_per_unit, row.fetched_at = value, utcnow()
        else:
            session.add(ExchangeRate(day=today, currency=cur, nok_per_unit=value))
    session.flush()
    log.info("fx_refreshed", currencies=len(rates), eur_nok=rates.get("EUR"))
    return FxRates(rates, today)


def get_rates(session: Session) -> FxRates:
    """Latest cached rates, or configured fallback rates if nothing has been fetched yet."""
    latest_day = session.scalar(select(ExchangeRate.day).order_by(ExchangeRate.day.desc()).limit(1))
    if latest_day:
        rows = session.scalars(select(ExchangeRate).where(ExchangeRate.day == latest_day)).all()
        return FxRates({r.currency: r.nok_per_unit for r in rows}, latest_day)
    log.warning("fx_using_fallback_rates")
    return FxRates(get_user_config().currencies.fallback_rates_nok, None, fallback=True)

"""Configuration.

Two layers:
* ``Settings`` — deployment settings and secrets, read from environment / ``.env``.
* ``UserConfig`` — user preferences (scoring, binders, alerts, sources) read from
  the YAML files in ``CONFIG_DIR``. Reloaded automatically when a file changes.
"""

from __future__ import annotations

import threading
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_ROOT / ".env", ".env"), extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./dev.db"
    config_dir: Path = REPO_ROOT / "config"
    data_dir: Path = REPO_ROOT / "data"
    log_level: str = "INFO"
    log_json: bool = False

    # Protects /api/v1/*. The web container injects it server-side.
    api_key: SecretStr | None = None

    cardtrader_api_token: SecretStr | None = None
    cardtrader_base_url: str = "https://api.cardtrader.com/api/v2"
    # "auto": mock when no token is configured; "true"/"false" to force.
    cardtrader_mock: str = "auto"

    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None
    # "auto": dry-run when token/chat id missing; "true" forces dry-run.
    telegram_dry_run: str = "auto"

    http_user_agent: str = "pokemon-deal-hunter/0.1 (self-hosted personal tool)"

    @property
    def cardtrader_is_mock(self) -> bool:
        if self.cardtrader_mock.lower() in ("true", "1", "yes"):
            return True
        if self.cardtrader_mock.lower() in ("false", "0", "no"):
            return False
        return not (self.cardtrader_api_token and self.cardtrader_api_token.get_secret_value())

    @property
    def telegram_is_dry_run(self) -> bool:
        if self.telegram_dry_run.lower() in ("true", "1", "yes"):
            return True
        token = self.telegram_bot_token.get_secret_value() if self.telegram_bot_token else ""
        return not (token and self.telegram_chat_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()


# --------------------------------------------------------------------------- YAML models


class PopularityTier(BaseModel):
    score: float
    names: list[str] = []


class PremiumTarget(BaseModel):
    name: str
    set_contains: str | None = None
    number: str | None = None
    rarity_contains: str | None = None


class PokemonConfig(BaseModel):
    popularity_tiers: dict[str, PopularityTier] = {}
    default_score: float = 0.3
    high_priority: list[str] = []
    ignored: list[str] = []
    themes: dict[str, list[str]] = {}
    premium_targets: list[PremiumTarget] = []


class SetMeta(BaseModel):
    name: str
    code: str
    aliases: list[str] = []
    release_date: date | None = None
    printed_total: int | None = None
    desirability: float = 0.5
    cardtrader_track: bool = False
    cardtrader_expansion: str | None = None  # CardTrader expansion code/name if it differs


class SetsConfig(BaseModel):
    default_desirability: float = 0.5
    sets: list[SetMeta] = []
    pack_counts: dict[str, int] = {}

    def find(self, name_or_code: str | None) -> SetMeta | None:
        if not name_or_code:
            return None
        key = name_or_code.strip().lower()
        for s in self.sets:
            if key in (s.name.lower(), s.code.lower()) or key in [a.lower() for a in s.aliases]:
                return s
        return None


class RarityRule(BaseModel):
    match: str
    score: float


class RaritiesConfig(BaseModel):
    scarcity: list[RarityRule] = []
    default_score: float = 0.2
    premium_rarities: list[str] = []

    def scarcity_for(self, rarity: str | None) -> float:
        r = (rarity or "").lower()
        for rule in self.scarcity:
            if rule.match in r:
                return rule.score
        return self.default_score

    def is_premium(self, rarity: str | None) -> bool:
        r = (rarity or "").lower()
        return any(p in r for p in self.premium_rarities)


class BinderModifiers(BaseModel):
    duplicate_in_premium: float = -8
    duplicate_other: float = -4
    duplicate_exceptional_discount: float = 0.35
    missing_high_priority: float = 8
    iconic_missing_from_binder: float = 5
    completes_set_or_theme: float = 5
    improves_diversification: float = 3
    max_total_bonus: float = 15


class BindersConfig(BaseModel):
    premium: dict[str, float] = {"min_raw_value_nok": 400, "preferred_max_buy_nok": 1500}
    regular: dict[str, float] = {"min_raw_value_nok": 50}
    modifiers: BinderModifiers = BinderModifiers()


class FairValueConfig(BaseModel):
    min_listings_for_executable: int = 5
    executable_weights: dict[str, float] = {"cheapest5": 0.60, "cheapest10": 0.25, "history30": 0.15}
    thin_market_history_weight: float = 0.4   # <5 listings: lean more on own history
    tail_ratio: float = 1.30                  # trimmed median > cheapest-5 × this → expensive tail
    low_outlier_ratio: float = 0.70           # lowest ask < cheapest-5 × this → outlier
    min_history_days: int = 5
    high_dispersion: float = 0.5
    high_volatility: float = 0.15
    trim_fraction: float = 0.2


class ScoringModifiers(BaseModel):
    seller_confidence_max_penalty: float = 12
    seller_confidence_neutral: float = 0.8
    match_confidence_penalty_per_0_1: float = 5
    lot_uncertainty_penalty: float = 8
    multi_item_bundle_penalty: float = 3
    watchlist_target_met_bonus: float = 8
    watchlist_high_priority_bonus: float = 3
    premium_value_bonus: float = 3


class ScoringConfig(BaseModel):
    weights: dict[str, float] = {
        "discount_to_fair_value": 30,
        "liquidity": 20,
        "pokemon_popularity": 15,
        "set_desirability": 10,
        "trend": 10,
        "grading_upside": 10,
        "scarcity": 5,
    }
    discount_curve: list[tuple[float, float]] = [(0, 0), (0.4, 1)]
    liquidity_curve: list[tuple[float, float]] = [(0, 0), (30, 1)]
    trend_curve: list[tuple[float, float]] = [(-0.2, 0), (0, 0.5), (0.25, 1)]
    unknown_trend_score: float = 0.4
    unknown_grading_score: float = 0.25
    bands: dict[str, float] = {"STEAL": 93, "STRONG_BUY": 85, "GOOD": 75, "WATCH": 60}
    modifiers: ScoringModifiers = ScoringModifiers()
    red_flags: list[str] = []
    fair_value: FairValueConfig = FairValueConfig()


class GoodRules(BaseModel):
    watchlist_target_met: bool = True
    high_priority_missing: bool = True
    premium_binder_fit: bool = True


class WatchDigest(BaseModel):
    enabled: bool = False
    hour: int = 19


class AlertsConfig(BaseModel):
    minimum_notification_fair_value_nok: float = 250
    minimum_discount_good: float = 0.15
    minimum_discount_strong_buy: float = 0.22
    minimum_discount_steal: float = 0.30
    suspicious_discount: float = 0.45       # deeper than this: warn + cap at STRONG_BUY
    min_match_confidence: float = 0.90
    min_fair_value_confidence: float = 0.5
    allow_damaged: bool = False
    damaged_conditions: list[str] = ["damaged", "poor", "played"]
    max_alerts_per_day: int = 5
    steal_ignores_daily_cap: bool = True
    repeat_cooldown_hours: float = 24
    repeat_min_price_drop: float = 0.10
    good_rules: GoodRules = GoodRules()
    watch_digest: WatchDigest = WatchDigest()
    source_health: dict[str, int] = {"failures_before_alert": 3}


class GradingConfig(BaseModel):
    estimated_grading_cost_nok: float = 450
    upside_curve: list[tuple[float, float]] = [(0, 0), (2, 1)]
    psa9_min_margin: float = 0.10


class CurrenciesConfig(BaseModel):
    base_currency: str = "NOK"
    display_currencies: list[str] = ["NOK", "EUR", "USD"]
    fx_provider_url: str = "https://api.frankfurter.dev/v1/latest"
    fallback_rates_nok: dict[str, float] = {"NOK": 1.0, "EUR": 11.7, "USD": 10.2}


class CardTraderSourceConfig(BaseModel):
    enabled: bool = True
    interval_minutes: int = 30
    requests_per_second: float = 2
    languages: list[str] = ["en"]
    accepted_conditions: list[str] = ["Mint", "Near Mint"]
    exclude_graded: bool = True
    exclude_reverse_holo: bool = True
    one_listing_per_seller: bool = True
    estimated_shipping_nok: float = 60
    track_sets_from_config: bool = True
    extra_expansion_codes: list[str] = []
    evaluate_cheapest_n: int = 3
    min_fair_value_to_evaluate_nok: float = 100


class FinnSourceConfig(BaseModel):
    enabled: bool = True
    fetch_metadata: bool = True
    estimated_shipping_nok: float = 0


class ShopConfig(BaseModel):
    name: str
    enabled: bool = False
    kind: str = "shopify"
    base_url: str
    collection: str | None = None
    currency: str = "NOK"
    estimated_shipping_nok: float = 0


class StoresSourceConfig(BaseModel):
    enabled: bool = False
    interval_minutes: int = 60
    requests_per_second: float = 0.5
    shops: list[ShopConfig] = []


class SchedulerConfig(BaseModel):
    fx_refresh_hour: int = 6
    maintenance_hour: int = 3
    portfolio_snapshot_hour: int = 4


class RetentionConfig(BaseModel):
    raw_snapshot_days: int = 30
    collector_run_days: int = 30
    listing_gone_after_days: int = 14
    evaluation_days: int = 90


class SourcesConfig(BaseModel):
    cardtrader: CardTraderSourceConfig = CardTraderSourceConfig()
    finn: FinnSourceConfig = FinnSourceConfig()
    stores: StoresSourceConfig = StoresSourceConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    retention: RetentionConfig = RetentionConfig()


class UserConfig(BaseModel):
    pokemon: PokemonConfig = PokemonConfig()
    sets: SetsConfig = SetsConfig()
    rarities: RaritiesConfig = RaritiesConfig()
    binders: BindersConfig = BindersConfig()
    scoring: ScoringConfig = ScoringConfig()
    alerts: AlertsConfig = AlertsConfig()
    grading: GradingConfig = GradingConfig()
    currencies: CurrenciesConfig = CurrenciesConfig()
    sources: SourcesConfig = SourcesConfig()


_CONFIG_FILES = ("pokemon", "sets", "rarities", "binders", "scoring", "alerts", "grading", "currencies",
                 "sources")
_lock = threading.Lock()
_cache: dict[str, Any] = {"mtimes": None, "config": None}


def load_user_config(config_dir: Path | None = None) -> UserConfig:
    """Load all YAML files from ``config_dir`` into a validated ``UserConfig``."""
    config_dir = config_dir or get_settings().config_dir
    raw: dict[str, Any] = {}
    for name in _CONFIG_FILES:
        path = config_dir / f"{name}.yaml"
        if path.exists():
            raw[name] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return UserConfig.model_validate(raw)


def get_user_config() -> UserConfig:
    """Cached config that reloads when any YAML file's mtime changes."""
    config_dir = get_settings().config_dir
    mtimes = tuple(
        (config_dir / f"{n}.yaml").stat().st_mtime if (config_dir / f"{n}.yaml").exists() else 0
        for n in _CONFIG_FILES
    )
    with _lock:
        if _cache["mtimes"] != mtimes:
            _cache["config"] = load_user_config(config_dir)
            _cache["mtimes"] = mtimes
        return _cache["config"]

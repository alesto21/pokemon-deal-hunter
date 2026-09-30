// Mirrors the dict shapes returned by apps/api/app/api/serializers.py and routes.

export type Recommendation = "IGNORE" | "WATCH" | "GOOD" | "STRONG_BUY" | "STEAL";

export interface Card {
  id: number;
  name: string;
  set_name: string | null;
  set_code: string | null;
  card_number: string | null;
  rarity: string | null;
  language: string;
  pokemon_name: string | null;
  release_date: string | null;
  image_url: string | null;
  is_promo: boolean;
  source_ids: Record<string, unknown>;
}

export interface Product {
  id: number;
  name: string;
  product_type: string;
  set_name: string | null;
  set_code: string | null;
  pack_count: number | null;
  language: string;
  release_date: string | null;
  image_url: string | null;
  source_ids: Record<string, unknown>;
}

export interface NotificationDecision {
  notify: boolean;
  severity: string | null;
  blocked_by: string[];
}

export interface Evaluation {
  id: number;
  timestamp: string;
  price_nok: number;
  fair_value_nok: number | null;
  fair_value_low: number | null;
  fair_value_high: number | null;
  fair_value_confidence: number | null;
  discount_pct: number | null;
  total_score: number;
  recommendation: Recommendation; // raw score band
  raw_band: Recommendation;
  alert_level: Recommendation; // effective level after caps — what the badge shows
  caps: string[];
  binder_fit: string | null;
  scores: {
    liquidity: number;
    popularity: number;
    set: number;
    trend: number;
    grading: number;
    scarcity: number;
    portfolio_points: number;
    seller_confidence: number;
  };
  trend_30d: number | null;
  median_30d: number | null;
  reasons: string[];
  warnings: string[];
  notification: NotificationDecision | null;
  details: Record<string, unknown>;
}

export interface MatchCandidate {
  entity_type: "card" | "product";
  entity_id: number;
  label: string;
  score: number;
  reasons: string[];
}

export interface Listing {
  id: number;
  source: string;
  external_id: string;
  url: string | null;
  title: string;
  seller: string | null;
  seller_rating: number | null;
  condition: string | null;
  language: string | null;
  listing_kind: string;
  is_graded: boolean;
  grade_company: string | null;
  grade: number | null;
  quantity: number;
  asking_price: number;
  currency: string;
  normalized_price_nok: number;
  shipping_price_nok: number;
  total_price_nok: number;
  seller_country: string | null;
  seller_region: string | null;
  import_buffer_nok: number;
  landed_cost_nok: number;
  first_seen: string;
  last_seen: string;
  status: string;
  matched_card_id: number | null;
  matched_product_id: number | null;
  entity_label: string | null;
  confidence: number;
  match_status: string;
  match_candidates: MatchCandidate[];
  image_urls: string[];
  evaluation: Evaluation | null;
}

export interface LotValuation {
  estimated_value_nok: number;
  conservative_value_nok: number;
  priced_items: number;
  total_items: number;
  lines: {
    id: number;
    label: string | null;
    card_id: number | null;
    product_id: number | null;
    quantity: number;
    unit_value_nok: number | null;
  }[];
}

export interface Lot {
  id: number;
  listing_id: number;
  notes: string | null;
  images: string[];
  valuation: LotValuation;
}

export interface ListingDetail extends Listing {
  evaluation_history: Evaluation[];
  lot?: { id: number; images: string[]; notes: string | null; valuation: LotValuation };
}

export interface DealsResponse {
  total: number;
  items: Listing[];
}

export interface PortfolioSummaryCore {
  total_cost_nok: number;
  raw_value_nok: number;
  graded_value_nok: number;
  total_value_nok: number;
  unrealized_gain_nok: number;
  unrealized_gain_pct: number | null;
  by_binder: Record<string, number>;
  change_30d_nok: number | null;
  item_count: number;
}

export interface OverviewSource {
  source: string;
  healthy: boolean;
  last_success: string | null;
  last_failure: string | null;
}

export interface Overview {
  scans_today: number;
  failed_scans_today: number;
  listings_processed_today: number;
  listings_evaluated_today: number;
  deals_found_today: number;
  alerts_sent_today: number;
  active_listings: number;
  review_queue: number;
  sources: OverviewSource[];
  portfolio: PortfolioSummaryCore;
  top_deals: Listing[];
}

export interface PortfolioItem {
  id: number;
  card_id: number | null;
  product_id: number | null;
  card: Card | null;
  product: Product | null;
  quantity: number;
  acquisition_price_nok: number;
  acquisition_date: string | null;
  binder_type: string;
  condition: string | null;
  grading_status: string;
  grade_company: string | null;
  psa_grade: number | null;
  notes: string | null;
}

export interface Holding extends PortfolioItem {
  unit_raw_value_nok: number | null;
  unit_graded_value_nok: number | null;
  cost_nok: number;
  value_nok: number;
  gain_nok: number;
  gain_pct: number | null;
}

export interface PortfolioSummary extends PortfolioSummaryCore {
  top_holdings: Holding[];
  best_performers: Holding[];
  worst_performers: Holding[];
  recent_purchases: Holding[];
  history: { day: string; cost: number; value: number }[];
}

export interface WatchlistItem {
  id: number;
  entity_id: number;
  target_type: "card" | "product";
  label: string | null;
  target_buy_price: number | null;
  priority: "high" | "normal" | "low";
  enabled: boolean;
  notes: string | null;
  fair_value_nok: number | null;
}

export interface FairValue {
  fair_value_nok: number | null;
  fair_value_low: number | null;
  fair_value_high: number | null;
  confidence: number;
  explanation: string[];
  flags: string[];
}

export interface HistoryStats {
  median_7d: number | null;
  median_30d: number | null;
  median_90d: number | null;
  median_all: number | null;
  days_30d: number;
  trend_30d: number | null;
  volatility_30d: number | null;
  avg_listing_count_30d: number | null;
}

export interface CurrentMarket {
  low: number | null;
  median: number | null;
  trimmed_median: number | null;
  cheapest5_median: number | null;
  listing_count: number;
  dispersion: number | null;
  cheapest3_median: number | null;
  cheapest10_median: number | null;
  has_expensive_tail: boolean;
  low_is_outlier: boolean;
}

export interface PriceHistory {
  entity_type: "card" | "product";
  entity_id: number;
  label: string;
  set_name: string | null;
  daily: {
    day: string;
    low: number | null;
    median: number | null;
    trimmed_median: number | null;
    cheapest5_median: number | null;
    cheapest10_median: number | null;
    listing_count: number | null;
  }[];
  raw: {
    timestamp: string;
    low: number | null;
    median: number | null;
    trimmed_median: number | null;
    cheapest5_median: number | null;
    cheapest10_median: number | null;
    listing_count: number;
    has_expensive_tail: boolean;
  }[];
  portfolio_entries: { date: string | null; price_nok: number; quantity: number }[];
  fair_value: FairValue;
  history: HistoryStats;
  current: CurrentMarket;
}

export interface SourceHealth {
  source: string;
  enabled: boolean;
  interval_minutes: number | null;
  mode: string;
  kind: "scheduled" | "manual";
  healthy: boolean | null;
  last_success: string | null;
  last_failure: string | null;
  last_error: string | null;
  consecutive_failures: number;
  running: boolean;
  runs_24h: number;
  error_rate_24h: number | null;
  last_duration_ms: number | null;
  last_items_fetched: number | null;
  last_items_matched: number | null;
}

export interface CollectorRun {
  id: number;
  source: string;
  started_at: string;
  finished_at: string | null;
  success: boolean;
  duration_ms: number | null;
  items_fetched: number;
  items_matched: number;
  listings_evaluated: number;
  deals_found: number;
  alerts_sent: number;
  error: string | null;
}

export interface AlertRow {
  id: number;
  kind: string;
  severity: string;
  sent_at: string;
  listing_id: number | null;
  price_nok: number | null;
  dry_run: boolean;
  telegram_message_id: number | null;
  message: string | null;
}

export interface SettingsResponse {
  environment: string;
  config_dir: string;
  secrets: Record<string, boolean>;
  modes: { cardtrader: string; telegram: string };
  user_config: Record<string, unknown>;
}

export interface TelegramTestResult {
  ok: boolean;
  message_id: number | null;
  dry_run: boolean;
  error: string | null;
}

export interface ImportResult {
  imported: number;
  failed: number;
  items: { row: number; listing_id: number; score: number; recommendation: Recommendation }[];
  errors: { row: number; error: string }[];
}

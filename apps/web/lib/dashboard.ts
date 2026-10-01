/**
 * Types for the read-only /api/v1/dashboard/* endpoints (apps/api/app/services/dashboard.py).
 * All timestamps are naive UTC strings; money is NOK; ratios are 0..1.
 */
import type { Recommendation } from "./types";

export interface EntityBrief {
  type: "card" | "product";
  id: number;
  name: string;
  set_name: string | null;
  set_code: string | null;
  image_url: string | null;
  // card
  pokemon?: string | null;
  number?: string | null;
  rarity?: string | null;
  // product
  product_type?: string;
  pack_count?: number | null;
}

export interface Notification {
  notify: boolean;
  severity: string | null;
  blocked_by: string[];
}

export interface DealRow {
  listing_id: number;
  url: string | null;
  title: string;
  source: string;
  seller: string | null;
  seller_country: string | null;
  seller_region: string | null;
  condition: string | null;
  listing_kind: string;
  status: string;
  entity: EntityBrief | null;
  price: {
    asking: number;
    currency: string;
    item_nok: number;
    shipping_nok: number;
    shipping_basis: "exact" | "estimated" | string; // exact = seller-stated / observed checkout quote
    fees_nok: number;
    fees_basis: "exact" | "estimated" | string;
    import_buffer_nok: number;
    landed_nok: number; // item + shipping + fees + import buffer — single-card delivered cost
    landed_cost_confidence: number | null;
    purchase_route: "direct" | "zero" | null | string; // CardTrader only
  };
  fair_value_nok: number | null;
  fair_value_low: number | null;
  fair_value_high: number | null;
  confidence: number | null;
  discount_pct: number | null;
  discount_nok: number | null;
  score: number;
  raw_band: Recommendation;
  level: Recommendation; // EFFECTIVE level (after caps) — use for badges
  caps: string[];
  warnings: string[];
  reasons: string[];
  notification: Notification | null;
  trend_30d: number | null;
  evaluated_at: string;
  binder_fit: string | null;
  first_seen: string;
  published_at: string | null;
  location: string | null;
  pickup_required: boolean;
  safety_flags: string[];
  capture_method: string | null; // manual | csv | capture | null (scanned sources)
  lot: { coverage: number | null; unidentified: number | null } | null;
}

export interface FinnSummary {
  discovery: { automated: boolean; reason: string; channels: string[] };
  counts: {
    total: number;
    added_today: number;
    active: number;
    matched: number;
    needs_review: number;
    lots: number;
    pickup_only: number;
    by_capture_method: Record<string, number>;
    last_added: string | null;
  };
  best: DealRow[];
  newest: DealRow[];
}

export interface MarketBrief {
  low: number | null;
  cheapest3: number | null;
  cheapest5: number | null;
  cheapest10: number | null;
  broad_median: number | null;
  trimmed_median: number | null;
  valid_listings: number;
  excluded_listings: number | null;
  sellers: number | null;
  dispersion: number | null;
  has_expensive_tail: boolean;
  observed_at: string;
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

export interface DealDetail extends DealRow {
  market: MarketBrief | null;
  history: HistoryStats | null;
  fair_value_explanation: string[];
  fair_value_flags: string[];
  components: Record<string, number>;
  weighted: Record<string, number>;
  modifiers: Record<string, number>;
  item_discount_pct: number | null;
  grading: { psa9_nok: number | null; psa10_nok: number | null; label: string; flags: string[] } | null;
  sealed: Record<string, unknown> | null;
  match: { status: string; confidence: number };
}

export interface DealsResponse {
  total: number;
  items: DealRow[];
}

export interface HoldingRow {
  id: number;
  kind: "raw" | "graded" | "sealed";
  entity: EntityBrief | null;
  binder_type: string;
  quantity: number;
  acquisition_price_nok: number;
  acquisition_date: string | null;
  added_at: string;
  condition: string | null;
  grading_status: "raw" | "submitted" | "at_grader" | "graded" | string;
  grade_company: string | null;
  grade: number | null;
  notes: string | null;
  unit_value_nok: number | null;
  value_priced: boolean;
  cost_nok: number;
  value_nok: number;
  gain_nok: number | null;
  gain_pct: number | null;
}

export interface Group {
  count: number;
  cost_nok: number;
  value_nok: number;
  gain_nok: number;
  gain_pct: number | null;
  unpriced: number; // items without a market price (valued at 0 in totals)
}

export interface PortfolioSummary {
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

export interface PortfolioHistory {
  points: { day: string; cost_nok: number; value_nok: number; gain_nok: number; by_binder: Record<string, number> }[];
  ready: boolean;
  message: string | null;
}

export interface PortfolioOverview {
  summary: PortfolioSummary;
  by_kind: { raw: Group; graded: Group; sealed: Group };
  allocation: { kind: string; value_nok: number; cost_nok: number; count: number }[];
  history: PortfolioHistory;
  top_performers: HoldingRow[];
  largest_positions: HoldingRow[];
  recent_additions: HoldingRow[];
}

/** GET dashboard/portfolio (the overview endpoint omits `holdings`). */
export interface PortfolioPage extends PortfolioOverview {
  holdings: HoldingRow[];
}

export interface SystemMini {
  source: string;
  healthy: boolean | null;
  mode: string;
  last_success: string | null;
  worker: WorkerSchedule;
  lock: ScanLock;
}

export interface Overview {
  portfolio: PortfolioOverview;
  kpis: {
    active_deals: number;
    watchlist_count: number;
    alerts_today: { live: number; dry_run: number; total: number };
    active_listings: number;
  };
  best_deals: DealRow[];
  near_deals: DealRow[]; // effective WATCH with ≥5% discount, shown only when fewer than 3 GOOD+ deals
  system: SystemMini[];
}

export interface Binder {
  binder_type: "premium" | "regular";
  capacity: number;
  slots_used: number;
  slots_free: number;
  over_capacity: boolean;
  pct_complete: number | null;
  summary: Group & { avg_card_value_nok: number | null };
  sets: { set_name: string; cards: number }[];
  top_cards: HoldingRow[];
  recent_additions: HoldingRow[];
  items: HoldingRow[];
}

export interface SealedRow extends HoldingRow {
  packs: number | null;
  nok_per_pack_acquired: number | null;
  nok_per_pack_now: number | null;
  analysis: {
    rip_score: number;
    hold_score: number;
    sealed_premium: number | null;
    loose_pack_value_nok: number | null;
    product_age_years: number | null;
    notes: string[];
  } | null;
}

export interface Sealed {
  summary: Group & { products: number; total_packs: number };
  items: SealedRow[];
}

export interface GradedRef {
  price_nok: number;
  source: string;
  updated_at: string;
  confidence: number;
}

export interface GradingRow extends HoldingRow {
  raw_value_nok: number | null;
  psa9: GradedRef | null;
  psa10: GradedRef | null;
  grading_cost_nok: number;
  psa9_net_nok: number | null;
  psa10_net_nok: number | null;
  upside_psa9: number | null;
  upside_psa10: number | null;
  grading_label: string;
  flags: string[];
  missing: string[];
}

export interface Grading {
  grading_cost_nok: number;
  candidates: GradingRow[];
  submitted: GradingRow[];
  at_grader: GradingRow[];
  returned: GradingRow[];
  counts: { candidates: number; submitted: number; at_grader: number; returned: number };
}

export interface WatchRow {
  id: number;
  entity: EntityBrief | null;
  target_type: "card" | "product";
  priority: "high" | "normal" | "low";
  enabled: boolean;
  notes: string | null;
  target_buy_price_nok: number | null;
  fair_value_nok: number | null;
  confidence: number;
  fair_value_flags: string[];
  market: { low: number | null; cheapest5: number | null; valid_listings: number };
  trend_30d: number | null;
  history_days: number;
  history: { day: string; cheapest5: number | null; low: number | null }[];
  best_listing: DealRow | null;
  best_discount_pct: number | null;
  below_target: boolean;
}

export interface Mover {
  entity_type: "card" | "product";
  entity_id: number;
  entity: EntityBrief | null;
  from_nok: number;
  to_nok: number;
  change_pct: number;
  from_day: string;
  to_day: string;
  days: number;
}

export interface Market {
  coverage: {
    observations: number;
    daily_rows: number;
    tracked_entities: number;
    tracked_cards: number;
    tracked_products: number;
    days_collected: number;
    first_day: string | null;
    last_day: string | null;
    first_observation: string | null;
    last_observation: string | null;
    entities_with_7_days: number;
    min_value_nok: number;
  };
  movers_ready: boolean;
  gainers: Mover[];
  decliners: Mover[];
  most_liquid: { entity_type: string; entity_id: number; entity: EntityBrief | null; valid_listings: number; cheapest5: number | null; low: number | null }[];
  strongest_discounts: DealRow[];
}

export interface MarketSeries {
  entity: EntityBrief;
  daily: { day: string; low: number | null; cheapest5: number | null; fair_value: number | null }[];
  history_ready: boolean;
  intraday: { timestamp: string; low: number | null; cheapest5: number | null; valid_listings: number }[];
  current: MarketBrief | null;
  fair_value: { value_nok: number | null; low: number | null; high: number | null; confidence: number; flags: string[]; explanation: string[] };
  history: HistoryStats;
}

export interface AlertRow {
  id: number;
  kind: "deal" | "health" | "digest" | "test" | string;
  sent_at: string;
  level: string;
  dry_run: boolean;
  delivered: boolean;
  telegram_message_id: number | null;
  price_nok: number | null;
  fair_value_nok: number | null;
  discount_pct: number | null;
  listing_id: number | null;
  url: string | null;
  source: string | null;
  entity: EntityBrief | null;
  title: string | null;
  message: string | null;
}

export interface BlockedRow {
  evaluation_id: number;
  timestamp: string;
  listing_id: number;
  url: string | null;
  source: string;
  entity: EntityBrief | null;
  title: string;
  level: Recommendation;
  price_nok: number;
  fair_value_nok: number | null;
  discount_pct: number | null;
  blocked_by: string[];
  cooldown: boolean;
  region_blocked: boolean;
}

export interface Alerts {
  summary: {
    today: number;
    window: number;
    window_days: number;
    by_level: Record<"GOOD" | "STRONG_BUY" | "STEAL", number>;
    live: number;
    dry_run: number;
    blocked: number;
    health_alerts: number;
  };
  alerts: AlertRow[];
  blocked: BlockedRow[];
}

export interface ScanLock {
  locked: boolean;
  owner: string | null;
  acquired_at: string | null;
  heartbeat_at: string | null;
  age_seconds: number | null;
  heartbeat_age_seconds: number | null;
  stale: boolean;
}

export interface WorkerSchedule {
  worker_scheduled: boolean;
  next_scheduled_scan: string | null;
  next_scan_overdue: boolean;
  next_scan_overdue_seconds: number | null;
  last_successful_scan: string | null;
}

export interface SystemInfo {
  overall_ok: boolean;
  database: { ok: boolean; migrations: string | null; dialect: string; migration_version: string | null; size_bytes: number | null };
  worker:
    | (WorkerSchedule & {
        lock: ScanLock;
        scans_24h: number;
        errors_24h: number;
        error_rate_24h: number | null;
        last_error: string | null;
        last_duration_ms: number | null;
        interval_minutes: number | null;
      })
    | null;
  sources: import("./types").SourceHealth[];
  telegram: { mode: string | null; configured: boolean; last_deal_alert_at: string | null };
  cardtrader: { mode: string | null };
  fx: { eur_nok: number | null; day: string | null };
  backups:
    | { configured: false }
    | { configured: true; count_daily: number; count_weekly: number; latest_file: string | null; latest_at: string | null; latest_size_bytes: number | null };
  diagnostics: {
    ready_checks: Record<string, string>;
    environment: string;
    recent_runs: { source: string; started_at: string; success: boolean; duration_ms: number | null; error: string | null }[];
  };
}

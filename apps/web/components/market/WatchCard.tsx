"use client";

import { ArrowUpRight, Pencil, Target, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { entitySub, entityTitle, sourceLabel } from "@/components/deals/bits";
import { Badge, CardThumb, LevelBadge, btn, btnDanger, btnGhost, btnPrimary, input } from "@/components/ui";
import type { WatchRow } from "@/lib/dashboard";
import { gainClass, nok, pct } from "@/lib/format";
import Sparkline from "./Sparkline";

const PRIORITY_TONE = { high: "gold", normal: "neutral", low: "neutral" } as const;

function Metric({ label, value, className = "" }: { label: string; value: React.ReactNode; className?: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] uppercase tracking-wider text-ink-3">{label}</div>
      <div className={`num truncate text-sm text-ink ${className}`}>{value}</div>
    </div>
  );
}

export default function WatchCard({
  w,
  onSave,
  onRemove,
}: {
  w: WatchRow;
  onSave: (id: number, body: { target_buy_price: number | null; priority: string }) => Promise<void>;
  onRemove: (id: number) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [target, setTarget] = useState(w.target_buy_price_nok?.toString() ?? "");
  const [priority, setPriority] = useState<string>(w.priority);
  const best = w.best_listing;
  const title = entityTitle(w.entity, "Unknown item");

  return (
    <article className={`rounded-xl border bg-surface p-4 ${w.below_target ? "border-gold/60 ring-1 ring-gold/30" : "border-line"}`}>
      <div className="flex gap-3">
        <CardThumb src={w.entity?.image_url} alt={title} />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="truncate font-medium text-ink">{title}</div>
              <div className="truncate text-xs text-ink-3">{entitySub(w.entity)}</div>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              {w.below_target && (
                <Badge tone="gold">
                  <Target size={11} /> at target
                </Badge>
              )}
              <Badge tone={PRIORITY_TONE[w.priority] ?? "neutral"}>{w.priority}</Badge>
            </div>
          </div>
          <div className="mt-1 text-xs text-ink-3">
            Target {w.target_buy_price_nok !== null ? <span className="text-ink-2">{nok(w.target_buy_price_nok)}</span> : "not set"}
            {!w.enabled && " · paused"}
          </div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-x-3 gap-y-2 sm:grid-cols-4">
        <Metric label="Fair value" value={nok(w.fair_value_nok)} className="text-gold" />
        <Metric label="Market low" value={nok(w.market.low)} />
        <Metric label="Cheapest-5" value={nok(w.market.cheapest5)} />
        <Metric label="Valid listings" value={w.market.valid_listings} />
        <Metric label="Confidence" value={pct(w.confidence, 0)} />
        <Metric label="30d trend" value={w.trend_30d === null ? "—" : pct(w.trend_30d, 1, true)} className={gainClass(w.trend_30d)} />
        <div className="col-span-3 sm:col-span-2">
          <div className="text-[10px] uppercase tracking-wider text-ink-3">Cheapest-5, 30 days</div>
          <Sparkline points={w.history.map((h) => h.cheapest5)} width={150} height={30} />
        </div>
      </div>

      <div className="mt-3 rounded-lg border border-line bg-surface-2 p-3">
        {best ? (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="text-[10px] uppercase tracking-wider text-ink-3">Best current listing</div>
              <div className="num text-sm">
                <span className="font-medium text-ink">{nok(best.price.landed_nok)}</span>
                <span className="text-ink-3"> landed · </span>
                <span className={gainClass(w.best_discount_pct)}>{pct(w.best_discount_pct)}</span>
              </div>
              <div className="truncate text-[11px] text-ink-3">
                {sourceLabel(best.source)} · {best.seller_country ?? "??"} ({best.seller_region ?? "?"})
              </div>
            </div>
            <div className="flex items-center gap-2">
              <LevelBadge level={best.level} />
              <Link href={`/deals?listing=${best.listing_id}`} className={btnGhost} aria-label="Deal detail">
                Details <ArrowUpRight size={13} />
              </Link>
            </div>
          </div>
        ) : (
          <div className="text-sm text-ink-3">No active evaluated listing right now.</div>
        )}
      </div>

      {editing ? (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input className={`${input} w-36`} type="number" min="0" step="any" placeholder="Target NOK" value={target} onChange={(e) => setTarget(e.target.value)} />
          <select className={`${input} w-32`} value={priority} onChange={(e) => setPriority(e.target.value)} aria-label="Priority">
            <option value="high">High</option>
            <option value="normal">Normal</option>
            <option value="low">Low</option>
          </select>
          <button
            className={btnPrimary}
            onClick={async () => {
              await onSave(w.id, { target_buy_price: target ? Number(target) : null, priority });
              setEditing(false);
            }}
          >
            Save
          </button>
          <button className={btn} onClick={() => setEditing(false)}>
            Cancel
          </button>
        </div>
      ) : (
        <div className="mt-3 flex items-center justify-between">
          <div className="flex gap-1">
            <button className={btnGhost} onClick={() => setEditing(true)}>
              <Pencil size={13} /> Edit
            </button>
            {w.entity?.type === "card" && (
              <Link className={btnGhost} href={`/market?type=card&id=${w.entity.id}`}>
                History
              </Link>
            )}
          </div>
          <button className={btnDanger} onClick={() => onRemove(w.id)} aria-label={`Remove ${title} from watchlist`}>
            <Trash2 size={12} /> Remove
          </button>
        </div>
      )}
    </article>
  );
}

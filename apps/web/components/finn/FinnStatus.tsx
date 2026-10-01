"use client";

import { Globe, MousePointerClick } from "lucide-react";
import Link from "next/link";
import { LevelBadge, StatTile } from "@/components/ui";
import { LandedValue } from "@/components/deals/cost";
import { entityTitle } from "@/components/deals/bits";
import type { DealRow, FinnSummary } from "@/lib/dashboard";
import { pct, rel } from "@/lib/format";

const METHOD: Record<string, string> = { capture: "browser capture", manual: "pasted URL", csv: "CSV import", unknown: "older" };

function Row({ d }: { d: DealRow }) {
  return (
    <li className="flex items-center gap-3 py-2 text-sm">
      <LevelBadge level={d.level} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-ink">{entityTitle(d.entity, d.title)}</div>
        <div className="flex flex-wrap gap-x-2 text-[11px] text-ink-3">
          <span>{d.location ?? "Norway"}</span>
          <span>added {rel(d.first_seen)}</span>
          {d.pickup_required && <span className="text-amber-300">pickup only</span>}
          {d.listing_kind === "lot" && <span className="text-sky-300">lot{d.lot?.coverage != null ? ` · ${pct(d.lot.coverage, 0)} identified` : ""}</span>}
          {d.safety_flags.length > 0 && <span className="text-amber-300/80" title={d.safety_flags.join("\n")}>{d.safety_flags.length} check{d.safety_flags.length > 1 ? "s" : ""}</span>}
        </div>
      </div>
      <div className="text-right text-xs">
        <LandedValue p={d.price} className="text-ink" />
        <div className={d.discount_pct && d.discount_pct > 0 ? "text-gain" : "text-ink-3"}>{pct(d.discount_pct)}</div>
      </div>
    </li>
  );
}

/** FINN visibility: counts, best/newest captured listings and how listings get in (never crawled). */
export function FinnStatus({ data, compact = false }: { data: FinnSummary; compact?: boolean }) {
  const c = data.counts;
  const methods = Object.entries(c.by_capture_method);
  const list = data.best.length ? data.best : data.newest;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start gap-2 rounded-lg border border-line bg-surface-2/50 px-3 py-2 text-xs text-ink-3">
        <Globe size={14} className="mt-0.5 shrink-0" />
        <span className="min-w-0 flex-1">
          Not crawled — {data.discovery.reason}. Listings arrive only when you add them:{" "}
          {data.discovery.channels.join(" · ")}.
        </span>
        <Link href="/capture" className="flex items-center gap-1 text-gold hover:underline">
          <MousePointerClick size={13} /> Capture
        </Link>
      </div>
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
        <StatTile label="Active" value={c.active} hint={`${c.total} total`} />
        <StatTile label="Today" value={c.added_today} hint={c.last_added ? `last ${rel(c.last_added)}` : "none yet"} />
        <StatTile label="Matched" value={c.matched} />
        <StatTile label="Review" value={c.needs_review} />
        <StatTile label="Lots" value={c.lots} />
        <StatTile label="Pickup" value={c.pickup_only} />
      </div>
      {!compact && methods.length > 0 && (
        <div className="text-xs text-ink-3">
          Added via {methods.map(([k, v]) => `${METHOD[k] ?? k} ${v}`).join(" · ")}
        </div>
      )}
      {list.length > 0 ? (
        <div>
          <div className="text-[11px] uppercase tracking-wider text-ink-3">{data.best.length ? "Best FINN deals" : "Newest FINN listings"}</div>
          <ul className="divide-y divide-line">{list.slice(0, compact ? 4 : 8).map((d) => <Row key={d.listing_id} d={d} />)}</ul>
        </div>
      ) : (
        <p className="text-sm text-ink-3">No FINN listings yet — open a FINN ad in your browser and use the capture bookmarklet.</p>
      )}
    </div>
  );
}

"use client";

import type { ReactNode } from "react";
import { CostNote, CostValue, LandedValue } from "@/components/deals/cost";
import { ArrowUpRight, ShieldAlert, Tag } from "lucide-react";
import Link from "next/link";
import { Badge, CardThumb, EmptyState, LevelBadge } from "@/components/ui";
import type { DealRow } from "@/lib/dashboard";
import { nok, num, pct } from "@/lib/format";

const SOURCE_LABEL: Record<string, string> = { cardtrader: "CardTrader", finn: "FINN", manual: "Manual" };

function sourceLabel(s: string) {
  return SOURCE_LABEL[s] ?? s.replace(/^store:/, "Store · ");
}

/** Accent strip by effective level: obvious, not loud. */
const ACCENT: Record<string, string> = {
  STEAL: "before:bg-rose-400",
  STRONG_BUY: "before:bg-orange-400",
  GOOD: "before:bg-emerald-400",
  WATCH: "before:bg-sky-400/60",
};

function PriceRow({ label, value, strong = false }: { label: string; value: ReactNode; strong?: boolean }) {
  return (
    <div className={`flex items-baseline justify-between gap-2 ${strong ? "text-ink" : "text-ink-3"}`}>
      <span className="text-xs">{label}</span>
      <span className={`num ${strong ? "text-sm font-semibold" : "text-xs"}`}>{value}</span>
    </div>
  );
}

export function DealCard({ d }: { d: DealRow }) {
  const e = d.entity;
  const note = d.caps[0] ?? d.warnings[0];
  const p = d.price;
  return (
    <article
      className={`relative flex flex-col overflow-hidden rounded-xl border border-line bg-surface-2 p-3.5 before:absolute before:inset-y-0 before:left-0 before:w-0.5 ${ACCENT[d.level] ?? "before:bg-line"}`}
    >
      <div className="flex gap-3">
        <CardThumb src={e?.image_url} alt={e?.name ?? d.title} size="md" />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="truncate text-sm font-semibold text-ink" title={e?.name ?? d.title}>
                {e?.name ?? d.title}
                {e?.number && <span className="ml-1 font-normal text-ink-3">{e.number}</span>}
              </h3>
              <div className="truncate text-xs text-ink-3">{e?.set_name ?? "—"}</div>
            </div>
            <LevelBadge level={d.level} />
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-ink-3">
            <span>{sourceLabel(d.source)}</span>
            <span aria-hidden>·</span>
            <span>
              {d.seller_country ?? "??"} · {d.seller_region ?? "?"}
            </span>
            <span aria-hidden>·</span>
            <span className="num">score {num(d.score, 1)}</span>
          </div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-0.5 rounded-lg bg-surface px-3 py-2">
        <PriceRow label="Item" value={nok(p.item_nok)} />
        <PriceRow label="Fair value" value={nok(d.fair_value_nok)} />
        <PriceRow label="Shipping" value={<CostValue value={p.shipping_nok} basis={p.shipping_basis} />} />
        <PriceRow label="Confidence" value={d.confidence !== null ? pct(d.confidence, 0) : "—"} />
        <PriceRow label="Fees" value={<CostValue value={p.fees_nok} basis={p.fees_basis} />} />
        <div />
        <PriceRow label="Import buffer" value={nok(p.import_buffer_nok)} />
        <div />
        <PriceRow label="Landed" value={<LandedValue p={p} />} strong />
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-xs text-ink-3">Discount</span>
          <span className="num text-sm font-semibold text-gain">{pct(d.discount_pct, 1)}</span>
        </div>
        <div />
        <div className="num text-right text-xs text-gain/80">{nok(d.discount_nok)} below fair</div>
      </div>
      <CostNote p={p} />

      {note && (
        <div className="mt-2 flex items-start gap-1.5 text-xs text-amber-200/90" title={note}>
          <ShieldAlert size={13} className="mt-0.5 shrink-0" />
          <span className="line-clamp-2">{note}</span>
        </div>
      )}

      <div className="mt-3 flex items-center gap-2">
        <Link href={`/deals?listing=${d.listing_id}`} className="flex-1 rounded-lg border border-line px-3 py-1.5 text-center text-xs font-medium text-ink-2 hover:bg-surface-3 hover:text-ink">
          Why is this a deal?
        </Link>
        {d.url && (
          <a href={d.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 rounded-lg bg-surface-3 px-3 py-1.5 text-xs font-medium text-ink hover:brightness-125">
            Listing <ArrowUpRight size={13} />
          </a>
        )}
      </div>
    </article>
  );
}

export function BestDeals({ best, near }: { best: DealRow[]; near: DealRow[] }) {
  return (
    <div className="space-y-4">
      {best.length ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {best.map((d) => (
            <DealCard key={d.listing_id} d={d} />
          ))}
        </div>
      ) : (
        <EmptyState icon={Tag} title="No GOOD-or-better deals right now">
          The scanner checks CardTrader every 30 minutes. Nothing currently clears the discount and confidence rules.
        </EmptyState>
      )}
      {near.length > 0 && (
        <>
          <div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-wider text-ink-3">
            Closest to a deal <Badge>watch level</Badge>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {near.map((d) => (
              <DealCard key={d.listing_id} d={d} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export { sourceLabel };

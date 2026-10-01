"use client";

import { LandedValue } from "./cost";
import { ExternalLink, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";
import { Badge, CardThumb } from "@/components/ui";
import type { DealRow, EntityBrief } from "@/lib/dashboard";
import { gainClass, nok, pct, rel } from "@/lib/format";

export function sourceLabel(source: string | null | undefined): string {
  if (!source) return "—";
  if (source === "cardtrader") return "CardTrader";
  if (source === "finn") return "FINN";
  if (source === "manual") return "Manual";
  if (source.startsWith("store:")) return source.slice(6);
  return source;
}

export function entityTitle(e: EntityBrief | null | undefined, fallback = "Unmatched listing"): string {
  if (!e) return fallback;
  return e.type === "card" && e.number ? `${e.name} ${e.number}` : e.name;
}

export function entitySub(e: EntityBrief | null | undefined): string {
  if (!e) return "";
  const parts = [e.set_name ?? e.set_code];
  if (e.type === "card" && e.rarity) parts.push(e.rarity);
  if (e.type === "product" && e.product_type && e.product_type !== "other") parts.push(e.product_type.replace(/_/g, " "));
  return parts.filter(Boolean).join(" · ");
}

/** Thumbnail + name + set line. */
export function EntityCell({ entity, fallback, size = "sm", extra }: { entity: EntityBrief | null; fallback?: string; size?: "sm" | "md"; extra?: ReactNode }) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <CardThumb src={entity?.image_url} alt={entityTitle(entity, fallback)} size={size} />
      <div className="min-w-0">
        <div className="truncate font-medium text-ink">{entityTitle(entity, fallback)}</div>
        <div className="truncate text-xs text-ink-3">{entitySub(entity) || fallback}</div>
        {extra}
      </div>
    </div>
  );
}

export function SellerTag({ country, region, source, deal }: { country: string | null; region: string | null; source?: string; deal?: DealRow }) {
  const finn = deal && deal.source === "finn";
  return (
    <div className="min-w-0 text-xs">
      {source && <div className="text-ink-2">{sourceLabel(source)}</div>}
      <div className="text-ink-3">
        {finn ? deal.location ?? "Norway" : `${country ?? "??"} · ${region ?? "unknown"}`}
      </div>
      {finn && (
        <div className="mt-0.5 flex flex-wrap items-center gap-1 text-[11px] text-ink-3">
          <span title="when this listing was added to Deal Hunter">added {rel(deal.first_seen)}</span>
          {deal.pickup_required && <span className="rounded bg-amber-500/15 px-1 text-amber-300">pickup</span>}
          {deal.listing_kind === "lot" && <span className="rounded bg-sky-500/15 px-1 text-sky-300">lot</span>}
        </div>
      )}
    </div>
  );
}

/** Landed cost with the item + shipping (+ import) breakdown underneath. */
export function LandedCell({ price }: { price: DealRow["price"] }) {
  return (
    <div className="num text-right">
      <div className="font-medium text-ink">
        <LandedValue p={price} />
      </div>
      <div className="text-[11px] text-ink-3">
        {nok(price.item_nok)} + {nok(price.shipping_nok).replace(" NOK", "")}
        {price.shipping_basis !== "exact" && <span className="text-amber-300"> est</span>}
        {price.fees_nok > 0 ? ` + ${nok(price.fees_nok).replace(" NOK", "")}` : ""}
        {price.import_buffer_nok > 0 ? ` + ${nok(price.import_buffer_nok).replace(" NOK", "")}` : ""}
      </div>
    </div>
  );
}

export function DiscountCell({ nokValue, pctValue }: { nokValue: number | null; pctValue: number | null }) {
  return (
    <div className="num text-right">
      <div className={`font-medium ${gainClass(pctValue)}`}>{pct(pctValue)}</div>
      <div className="text-[11px] text-ink-3">{nok(nokValue)}</div>
    </div>
  );
}

export function ConfidenceTag({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined) return <span className="text-ink-3">—</span>;
  const tone = value >= 0.8 ? "gain" : value >= 0.5 ? "neutral" : "warn";
  return (
    <Badge tone={tone} title="Fair-value confidence (0–100%)">
      {pct(value, 0)}
    </Badge>
  );
}

/** The single most important caveat for a deal row: a cap first, then a warning. */
export function TopNote({ deal }: { deal: Pick<DealRow, "caps" | "warnings"> }) {
  const note = deal.caps[0] ?? deal.warnings[0];
  if (!note) return null;
  return (
    <div className="mt-1 flex items-start gap-1 text-[11px] text-amber-300/90" title={note}>
      <ShieldAlert size={12} className="mt-px shrink-0" />
      <span className="line-clamp-1">{note}</span>
    </div>
  );
}

export function OpenListing({ url, className = "" }: { url: string | null; className?: string }) {
  if (!url) return null;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => e.stopPropagation()}
      className={`inline-flex items-center gap-1 text-xs text-ink-2 hover:text-gold ${className}`}
    >
      Open <ExternalLink size={12} />
    </a>
  );
}

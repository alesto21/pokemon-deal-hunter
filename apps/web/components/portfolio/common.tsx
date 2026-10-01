"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Badge, CardThumb, Delta } from "@/components/ui";
import type { EntityBrief, HoldingRow } from "@/lib/dashboard";
import { nok } from "@/lib/format";

/** "Gastly · 177/162" style primary label. */
export function entityName(e: EntityBrief | null | undefined): string {
  if (!e) return "Unknown item";
  return e.number ? `${e.name} · ${e.number}` : e.name;
}

export function entitySub(e: EntityBrief | null | undefined): string {
  if (!e) return "";
  if (e.type === "product") return [e.set_name, e.product_type?.replaceAll("_", " ")].filter(Boolean).join(" · ");
  return [e.set_name, e.rarity].filter(Boolean).join(" · ");
}

const KIND_LABEL: Record<string, string> = { raw: "Raw card", graded: "Graded", sealed: "Sealed" };

export function KindBadge({ kind }: { kind: string }) {
  const tone = kind === "graded" ? "gold" : kind === "sealed" ? "info" : "neutral";
  return <Badge tone={tone}>{KIND_LABEL[kind] ?? kind}</Badge>;
}

const GRADING_LABEL: Record<string, string> = {
  raw: "Raw",
  submitted: "Submitted",
  at_grader: "At grader",
  graded: "Graded",
};

export function GradingBadge({ status, company, grade }: { status: string; company?: string | null; grade?: number | null }) {
  if (status === "graded" && grade) return <Badge tone="gold">{`${company ?? "PSA"} ${grade}`}</Badge>;
  const tone = status === "raw" ? "neutral" : "info";
  return <Badge tone={tone}>{GRADING_LABEL[status] ?? status}</Badge>;
}

export const GRADING_OPTIONS = [
  { value: "raw", label: "Raw" },
  { value: "submitted", label: "Submitted" },
  { value: "at_grader", label: "At grader" },
  { value: "graded", label: "Graded / returned" },
];

/** Compact holding line for "Top performers", "Largest positions", "Recent additions". */
export function HoldingLine({ h, right }: { h: HoldingRow; right?: ReactNode }) {
  return (
    <div className="flex items-center gap-3 py-2">
      <CardThumb src={h.entity?.image_url} alt={h.entity?.name ?? ""} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm text-ink">
          {entityName(h.entity)}
          {h.quantity > 1 && <span className="ml-1 text-ink-3">×{h.quantity}</span>}
        </div>
        <div className="truncate text-xs text-ink-3">{entitySub(h.entity)}</div>
      </div>
      <div className="shrink-0 text-right">
        {right ?? (
          <>
            <div className="num text-sm text-ink">{h.value_priced ? nok(h.value_nok) : "No price"}</div>
            <div className="text-xs">
              <Delta pctValue={h.gain_pct} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function HoldingList({ rows, empty, right }: { rows: HoldingRow[]; empty: ReactNode; right?: (h: HoldingRow) => ReactNode }) {
  if (!rows.length) return <div className="py-6 text-center text-sm text-ink-3">{empty}</div>;
  return (
    <div className="divide-y divide-line/70">
      {rows.map((h) => (
        <HoldingLine key={h.id} h={h} right={right?.(h)} />
      ))}
    </div>
  );
}

/** Honest note for items without a market price (they count as 0 in totals). */
export function UnpricedNote({ count }: { count: number }) {
  if (!count) return null;
  return (
    <div className="rounded-lg border border-warn/30 bg-warn/5 px-3 py-2 text-xs text-amber-200">
      {count} item{count === 1 ? " has" : "s have"} no market price yet and count as 0 NOK in value totals.
    </div>
  );
}

export function AddFirstCta({ label = "Add your first card" }: { label?: string }) {
  return (
    <Link href="/portfolio?add=1" className="inline-flex items-center gap-1.5 rounded-lg bg-gold px-3 py-1.5 text-sm font-semibold text-canvas hover:brightness-110">
      {label}
    </Link>
  );
}

"use client";

import Link from "next/link";
import { Fragment, useState } from "react";
import { nok, num, pct } from "@/lib/format";
import type { Listing } from "@/lib/types";
import { Empty, RecBadge, btn, td, th } from "./ui";

function DealDetail({ l }: { l: Listing }) {
  const ev = l.evaluation;
  if (!ev) return <div className="text-sm text-zinc-500">Not evaluated yet.</div>;
  return (
    <div className="grid gap-4 text-sm md:grid-cols-3">
      <div>
        <div className="mb-1 font-semibold">Why</div>
        {ev.reasons.length ? (
          <ul className="list-disc pl-5">{ev.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
        ) : (
          <div className="text-zinc-500">—</div>
        )}
        {ev.warnings.length > 0 && (
          <>
            <div className="mb-1 mt-3 font-semibold">Caveats</div>
            <ul className="list-disc pl-5 text-amber-700 dark:text-amber-400">{ev.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
          </>
        )}
      </div>
      <div>
        <div className="mb-1 font-semibold">Component scores</div>
        <table className="w-full text-xs">
          <tbody>
            {Object.entries(ev.scores).map(([k, v]) => (
              <tr key={k}>
                <td className="py-0.5 pr-2 text-zinc-500">{k.replace(/_/g, " ")}</td>
                <td className="py-0.5 tabular-nums">{num(v, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="mt-2 text-xs text-zinc-500">
          Fair value range {nok(ev.fair_value_low)} – {nok(ev.fair_value_high)} · confidence {num(ev.fair_value_confidence, 2)}
        </div>
      </div>
      <div>
        <div className="mb-1 font-semibold">Notification</div>
        {ev.notification ? (
          <div className="text-xs">
            <div>
              {ev.notification.notify ? "✅ would notify" : "⛔ not notified"} · severity {ev.notification.severity ?? "—"}
            </div>
            {ev.notification.blocked_by.length > 0 && (
              <ul className="mt-1 list-disc pl-5 text-zinc-500">{ev.notification.blocked_by.map((b) => <li key={b}>{b}</li>)}</ul>
            )}
          </div>
        ) : (
          <div className="text-xs text-zinc-500">No notification decision recorded.</div>
        )}
        <div className="mt-3 text-xs text-zinc-500">
          Match: {l.match_status} ({num(l.confidence, 2)}) · {l.condition ?? "condition ?"} · {l.language ?? "lang ?"} · seller {l.seller ?? "?"}
        </div>
      </div>
    </div>
  );
}

export default function DealsTable({ items, compact = false }: { items: Listing[]; compact?: boolean }) {
  const [open, setOpen] = useState<number | null>(null);
  if (!items.length) return <Empty>No deals match.</Empty>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px]">
        <thead className="border-b border-zinc-200 dark:border-zinc-800">
          <tr>
            <th className={th}>Listing</th>
            <th className={th}>Source</th>
            <th className={`${th} text-right`}>Total</th>
            <th className={`${th} text-right`}>Fair value</th>
            <th className={`${th} text-right`}>Discount</th>
            {!compact && <th className={`${th} text-right`}>30d trend</th>}
            <th className={`${th} text-right`}>Score</th>
            <th className={th}>Rec.</th>
            <th className={th}></th>
          </tr>
        </thead>
        <tbody>
          {items.map((l) => {
            const ev = l.evaluation;
            const isOpen = open === l.id;
            return (
              <Fragment key={l.id}>
                <tr
                  className="cursor-pointer border-b border-zinc-100 hover:bg-zinc-50 dark:border-zinc-900 dark:hover:bg-zinc-900/50"
                  onClick={() => setOpen(isOpen ? null : l.id)}
                >
                  <td className={td}>
                    <div className="font-medium">{l.entity_label ?? l.title}</div>
                    {l.entity_label && <div className="max-w-md truncate text-xs text-zinc-500">{l.title}</div>}
                    <div className="text-xs text-zinc-400">
                      {l.listing_kind}
                      {ev?.binder_fit && ev.binder_fit !== "none" ? ` · binder: ${ev.binder_fit}` : ""}
                    </div>
                  </td>
                  <td className={td}>{l.source}</td>
                  <td className={`${td} text-right tabular-nums`}>{nok(l.total_price_nok)}</td>
                  <td className={`${td} text-right tabular-nums`}>{nok(ev?.fair_value_nok)}</td>
                  <td className={`${td} text-right tabular-nums`}>{pct(ev?.discount_pct)}</td>
                  {!compact && <td className={`${td} text-right tabular-nums`}>{pct(ev?.trend_30d, 1, true)}</td>}
                  <td className={`${td} text-right font-semibold tabular-nums`}>{num(ev?.total_score)}</td>
                  <td className={td}>
                    <RecBadge rec={ev?.recommendation} />
                  </td>
                  <td className={`${td} whitespace-nowrap text-right`} onClick={(e) => e.stopPropagation()}>
                    {l.url && (
                      <a className={btn} href={l.url} target="_blank" rel="noopener noreferrer">
                        Open ↗
                      </a>
                    )}
                    {!compact && (
                      <Link className={`${btn} ml-1`} href={`/lots/${l.id}`} title="Lot / collection breakdown">
                        Lot
                      </Link>
                    )}
                  </td>
                </tr>
                {isOpen && (
                  <tr className="border-b border-zinc-100 bg-zinc-50/60 dark:border-zinc-900 dark:bg-zinc-900/40">
                    <td colSpan={compact ? 8 : 9} className="px-4 py-3">
                      <DealDetail l={l} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

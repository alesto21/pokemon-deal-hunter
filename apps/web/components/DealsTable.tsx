"use client";

import Link from "next/link";
import { Fragment, useState } from "react";
import { nok, num, pct } from "@/lib/format";
import type { Listing } from "@/lib/types";
import { Empty, RecBadge, btn, td, th } from "./ui";

function CostBreakdown({ l }: { l: Listing }) {
  const rows: [string, number][] = [
    [`Item (${l.asking_price.toFixed(2)} ${l.currency})`, l.normalized_price_nok],
    ["Shipping (est.)", l.shipping_price_nok],
    ["Import buffer (est.)", l.import_buffer_nok],
  ];
  return (
    <div className="mb-3">
      <div className="mb-1 font-semibold">Landed cost</div>
      <table className="w-full text-xs">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <td className="py-0.5 pr-2 text-zinc-500">{k}</td>
              <td className="py-0.5 text-right tabular-nums">{nok(v)}</td>
            </tr>
          ))}
          <tr className="border-t border-zinc-200 font-semibold dark:border-zinc-700">
            <td className="py-0.5 pr-2">Landed</td>
            <td className="py-0.5 text-right tabular-nums">{nok(l.landed_cost_nok)}</td>
          </tr>
        </tbody>
      </table>
      <div className="mt-1 text-xs text-zinc-500">
        Seller {l.seller_country ?? "unknown country"} · region {l.seller_region ?? "?"}. Estimates, not exact tax.
      </div>
    </div>
  );
}

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
        <CostBreakdown l={l} />
        <div className="mb-1 font-semibold">Recommendation</div>
        <div className="mb-3 text-xs">
          <div>
            Score {num(ev.total_score, 1)} → band <b>{ev.raw_band.replace("_", " ")}</b> → effective{" "}
            <b>{ev.alert_level.replace("_", " ")}</b>
          </div>
          {ev.caps.length > 0 ? (
            <ul className="mt-1 list-disc pl-5 text-amber-700 dark:text-amber-400">{ev.caps.map((c) => <li key={c}>{c}</li>)}</ul>
          ) : (
            <div className="mt-1 text-zinc-500">No caps applied.</div>
          )}
        </div>
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
            <th className={`${th} text-right`}>Landed</th>
            <th className={`${th} text-right`}>Fair value</th>
            <th className={`${th} text-right`}>Discount</th>
            {!compact && <th className={`${th} text-right`}>30d trend</th>}
            <th className={`${th} text-right`}>Score</th>
            <th className={th} title="Effective level after the discount cap and suspicious-price guard">Level</th>
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
                  <td className={td}>
                    <div>{l.source}</div>
                    <div className="text-xs text-zinc-500">
                      {l.seller_country ?? "??"} · {l.seller_region ?? "?"}
                      {ev?.notification?.blocked_by.some((b) => b.startsWith("seller_region_not_allowed")) && (
                        <span className="ml-1 rounded bg-zinc-200 px-1 text-[10px] uppercase dark:bg-zinc-800">no alert</span>
                      )}
                    </div>
                  </td>
                  <td className={`${td} text-right tabular-nums`}>
                    <div className="whitespace-nowrap font-medium">{nok(l.landed_cost_nok)}</div>
                    <div className="text-xs text-zinc-500">
                      {nok(l.normalized_price_nok)} + {nok(l.shipping_price_nok)}
                      {l.import_buffer_nok > 0 ? ` + ${nok(l.import_buffer_nok)}` : ""}
                    </div>
                  </td>
                  <td className={`${td} whitespace-nowrap text-right tabular-nums`}>{nok(ev?.fair_value_nok)}</td>
                  <td className={`${td} text-right tabular-nums`}>{pct(ev?.discount_pct)}</td>
                  {!compact && <td className={`${td} text-right tabular-nums`}>{pct(ev?.trend_30d, 1, true)}</td>}
                  <td className={`${td} text-right font-semibold tabular-nums`}>{num(ev?.total_score, 1)}</td>
                  <td className={td}>
                    <RecBadge rec={ev?.alert_level} />
                    {ev && ev.raw_band !== ev.alert_level && (
                      <div className="mt-0.5 text-[10px] text-zinc-500" title={ev.caps.join("\n")}>
                        capped · band {ev.raw_band.replace("_", " ")}
                      </div>
                    )}
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

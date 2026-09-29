"use client";

import Link from "next/link";
import DealsTable from "@/components/DealsTable";
import { ErrorBox, HealthDot, Loading, PageHeader, Panel, StatTile, btn } from "@/components/ui";
import { useApi } from "@/lib/api";
import { dt, gainClass, nok, pct } from "@/lib/format";
import type { Overview } from "@/lib/types";

export default function OverviewPage() {
  const { data, error, loading, reload } = useApi<Overview>("overview");
  const p = data?.portfolio;
  return (
    <>
      <PageHeader
        title="Overview"
        subtitle="Today's scanning activity, deals and portfolio at a glance"
        actions={<button className={btn} onClick={reload}>Refresh</button>}
      />
      <ErrorBox error={error} />
      <Loading show={loading && !data} />
      {data && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <StatTile label="Scans today" value={data.scans_today} hint={data.failed_scans_today ? `${data.failed_scans_today} failed` : undefined} />
            <StatTile label="Listings processed" value={data.listings_processed_today} hint={`${data.listings_evaluated_today} evaluated`} />
            <StatTile label="Deals found" value={data.deals_found_today} hint="GOOD or better" />
            <StatTile label="Alerts sent" value={data.alerts_sent_today} />
            <StatTile label="Active listings" value={data.active_listings} />
            <StatTile label="Review queue" value={<Link href="/review" className="underline-offset-2 hover:underline">{data.review_queue}</Link>} />
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <Panel title="Portfolio" className="lg:col-span-2">
              {p && (
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  <StatTile label="Value" value={nok(p.total_value_nok)} hint={`${p.item_count} items`} />
                  <StatTile label="Spent" value={nok(p.total_cost_nok)} />
                  <StatTile
                    label="Unrealized"
                    value={nok(p.unrealized_gain_nok)}
                    hint={pct(p.unrealized_gain_pct, 1, true)}
                    className={gainClass(p.unrealized_gain_nok)}
                  />
                  <StatTile
                    label="30-day change"
                    value={p.change_30d_nok === null ? "—" : nok(p.change_30d_nok)}
                    hint={p.change_30d_nok === null ? "needs 30 days of snapshots" : undefined}
                    className={gainClass(p.change_30d_nok)}
                  />
                </div>
              )}
            </Panel>
            <Panel title="Source health" actions={<Link href="/sources" className="text-xs text-zinc-500 hover:underline">details →</Link>}>
              {data.sources.length === 0 ? (
                <div className="text-sm text-zinc-500">No collector has run yet.</div>
              ) : (
                <ul className="space-y-2 text-sm">
                  {data.sources.map((s) => (
                    <li key={s.source} className="flex items-center justify-between gap-2">
                      <span className="flex items-center gap-2">
                        <HealthDot healthy={s.healthy} /> {s.source}
                      </span>
                      <span className="text-xs text-zinc-500">last ok {dt(s.last_success)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>

          <Panel title="Top active deals" actions={<Link href="/deals" className="text-xs text-zinc-500 hover:underline">all deals →</Link>}>
            <DealsTable items={data.top_deals} compact />
          </Panel>
        </div>
      )}
    </>
  );
}

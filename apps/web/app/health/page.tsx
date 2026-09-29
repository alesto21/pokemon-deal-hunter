"use client";

import { Fragment, useState } from "react";
import RunsTable from "@/components/RunsTable";
import { Empty, ErrorBox, Loading, PageHeader, Panel, RecBadge, btn, td, th } from "@/components/ui";
import { useApi } from "@/lib/api";
import { dt, nok } from "@/lib/format";
import type { AlertRow, CollectorRun } from "@/lib/types";

const SOURCES = ["cardtrader", "stores"];

export default function HealthPage() {
  const [source, setSource] = useState("cardtrader");
  const runs = useApi<CollectorRun[]>(`sources/${source}/runs?limit=100`);
  const alerts = useApi<AlertRow[]>("alerts?limit=100");
  const [open, setOpen] = useState<number | null>(null);

  return (
    <>
      <PageHeader
        title="Collector health"
        subtitle="Run history per collector, and every alert sent (deal, health, digest, test)."
        actions={<button className={btn} onClick={() => { runs.reload(); alerts.reload(); }}>Refresh</button>}
      />
      <Panel
        title="Run history"
        actions={
          <select className="rounded border border-zinc-300 bg-white px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900" value={source} onChange={(e) => setSource(e.target.value)}>
            {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        }
      >
        <ErrorBox error={runs.error} />
        <Loading show={runs.loading && !runs.data} />
        {runs.data && <RunsTable runs={runs.data} />}
      </Panel>
      <Panel title="Recent alerts" className="mt-6">
        <ErrorBox error={alerts.error} />
        <Loading show={alerts.loading && !alerts.data} />
        {alerts.data && alerts.data.length === 0 && <Empty>No alerts yet.</Empty>}
        {alerts.data && alerts.data.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[600px]">
              <thead className="border-b border-zinc-200 dark:border-zinc-800">
                <tr>
                  <th className={th}>Sent</th>
                  <th className={th}>Kind</th>
                  <th className={th}>Severity</th>
                  <th className={`${th} text-right`}>Price</th>
                  <th className={th}>Delivery</th>
                  <th className={th}>Listing</th>
                </tr>
              </thead>
              <tbody>
                {alerts.data.map((a) => (
                  <Fragment key={a.id}>
                    <tr className="cursor-pointer border-b border-zinc-100 hover:bg-zinc-50 dark:border-zinc-900 dark:hover:bg-zinc-900/50" onClick={() => setOpen(open === a.id ? null : a.id)}>
                      <td className={`${td} whitespace-nowrap`}>{dt(a.sent_at)}</td>
                      <td className={td}>{a.kind}</td>
                      <td className={td}>{a.kind === "deal" ? <RecBadge rec={a.severity} /> : a.severity}</td>
                      <td className={`${td} text-right tabular-nums`}>{nok(a.price_nok)}</td>
                      <td className={td}>{a.dry_run ? <span className="text-amber-600">dry-run</span> : a.telegram_message_id ? "sent" : "failed?"}</td>
                      <td className={td}>{a.listing_id ?? "—"}</td>
                    </tr>
                    {open === a.id && a.message && (
                      <tr className="border-b border-zinc-100 dark:border-zinc-900">
                        <td colSpan={6} className="px-4 py-3">
                          <pre className="whitespace-pre-wrap text-xs">{a.message.replace(/<[^>]+>/g, "")}</pre>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}

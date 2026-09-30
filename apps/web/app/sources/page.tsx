"use client";

import { useState } from "react";
import RunsTable from "@/components/RunsTable";
import { ErrorBox, HealthDot, Loading, PageHeader, Panel, btn } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { dt, pct } from "@/lib/format";
import type { CollectorRun, SourceHealth } from "@/lib/types";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 py-0.5 text-sm">
      <span className="text-zinc-500">{label}</span>
      <span className="text-right tabular-nums">{value}</span>
    </div>
  );
}

export default function SourcesPage() {
  const { data, error, loading, reload } = useApi<SourceHealth[]>("sources");
  const runs = useApi<CollectorRun[]>("sources/cardtrader/runs?limit=20");
  const [msg, setMsg] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function runNow(source: string) {
    setActionError(null);
    try {
      await api(`sources/${source}/run`, { method: "POST" });
      setMsg(`Queued ${source} — refresh in a moment.`);
      setTimeout(() => {
        reload();
        runs.reload();
      }, 3000);
    } catch (e) {
      setActionError((e as Error).message);
    }
  }

  return (
    <>
      <PageHeader
        title="Sources"
        subtitle="Collector configuration and health. FINN is manual URL ingestion only — it is never crawled."
        actions={<button className={btn} onClick={() => { reload(); runs.reload(); }}>Refresh</button>}
      />
      <ErrorBox error={error ?? actionError} />
      {msg && <div className="mb-4 text-sm text-emerald-700 dark:text-emerald-400">{msg}</div>}
      <Loading show={loading && !data} />
      {data && (
        <div className="grid gap-4 md:grid-cols-3">
          {data.map((s) => (
            <Panel
              key={s.source}
              title={s.source}
              actions={
                <span className="flex items-center gap-2 text-xs text-zinc-500">
                  <HealthDot healthy={s.healthy} />
                  {s.healthy === null ? "disabled" : s.healthy ? "healthy" : "unhealthy"}
                  {s.running && !s.worker.next_scan_overdue && " · running"}
                  {s.worker.next_scan_overdue && (
                    <span className="rounded bg-red-600 px-1.5 py-0.5 font-semibold text-white">WORKER OVERDUE</span>
                  )}
                </span>
              }
            >
              <Row label="Mode" value={s.mode} />
              <Row label="Type" value={s.kind} />
              <Row label="Enabled" value={s.enabled ? "yes" : "no"} />
              <Row label="Interval" value={s.interval_minutes ? `${s.interval_minutes} min` : "—"} />
              <Row label="Last successful scan" value={dt(s.worker.last_successful_scan)} />
              {s.kind === "scheduled" && (
                <>
                  <Row
                    label="Next scheduled scan"
                    value={
                      s.worker.next_scan_overdue ? (
                        <span className="font-semibold text-red-600 dark:text-red-400">
                          OVERDUE {Math.round((s.worker.next_scan_overdue_seconds ?? 0) / 60)} min (was due{" "}
                          {dt(s.worker.next_scheduled_scan)})
                        </span>
                      ) : s.worker.next_scheduled_scan ? (
                        dt(s.worker.next_scheduled_scan)
                      ) : s.enabled ? (
                        "not scheduled (worker stopped)"
                      ) : (
                        "—"
                      )
                    }
                  />
                  <Row
                    label="Scan lock"
                    value={
                      !s.scan_lock.locked
                        ? "free"
                        : s.scan_lock.stale
                          ? `STALE (heartbeat ${Math.round(s.scan_lock.heartbeat_age_seconds ?? 0)} s ago)`
                          : `held ${Math.round(s.scan_lock.age_seconds ?? 0)} s`
                    }
                  />
                  {s.scan_lock.locked && (
                    <div className="truncate text-right text-xs text-zinc-500" title={s.scan_lock.owner ?? ""}>
                      {s.scan_lock.owner} · since {dt(s.scan_lock.acquired_at)}
                    </div>
                  )}
                </>
              )}
              <Row label="Last failure" value={dt(s.last_failure)} />
              <Row label="Consecutive failures" value={s.consecutive_failures} />
              <Row label="Runs (24h)" value={s.runs_24h} />
              <Row label="Error rate (24h)" value={pct(s.error_rate_24h, 0)} />
              <Row label="Last duration" value={s.last_duration_ms !== null ? `${(s.last_duration_ms / 1000).toFixed(1)} s` : "—"} />
              <Row label="Fetched / matched" value={`${s.last_items_fetched ?? "—"} / ${s.last_items_matched ?? "—"}`} />
              {s.last_error && <div className="mt-2 break-words rounded bg-red-50 p-2 text-xs text-red-700 dark:bg-red-950 dark:text-red-300">{s.last_error}</div>}
              {s.kind === "scheduled" && (
                <button className={`${btn} mt-3`} disabled={!s.enabled || s.running} onClick={() => runNow(s.source)}>
                  Run now
                </button>
              )}
            </Panel>
          ))}
        </div>
      )}
      <Panel title="Recent CardTrader runs" className="mt-6">
        <ErrorBox error={runs.error} />
        {runs.data && <RunsTable runs={runs.data} />}
      </Panel>
    </>
  );
}

"use client";

import { Globe, MousePointerClick, Play, RadioTower, RefreshCw, Store, type LucideIcon } from "lucide-react";
import { useState } from "react";
import Link from "next/link";
import { FinnStatus } from "@/components/finn/FinnStatus";
import RunsTable from "@/components/sources/RunsTable";
import StatusCard, { type Status } from "@/components/system/StatusCard";
import { LockRows, NextScan, fmtSeconds } from "@/components/system/WorkerRows";
import { ErrorBox, Field, Loading, PageHeader, Panel, Segmented, btn } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { dt, pct, rel } from "@/lib/format";
import type { FinnSummary } from "@/lib/dashboard";
import type { CollectorRun, SourceHealth } from "@/lib/types";

const META: Record<string, { title: string; icon: LucideIcon; blurb: string }> = {
  cardtrader: { title: "CardTrader", icon: RadioTower, blurb: "Official API · primary pricing and listings" },
  finn: { title: "FINN", icon: Globe, blurb: "Browser capture, pasted URL or CSV — never crawled (FINN's terms prohibit it)" },
  stores: { title: "Web shops", icon: Store, blurb: "Public Shopify products.json · opt-in per shop" },
};

function status(s: SourceHealth): { status: Status; label: string } {
  if (!s.enabled) return { status: "off", label: "Disabled" };
  if (s.worker?.next_scan_overdue) return { status: "bad", label: "Worker overdue" };
  if (s.healthy === false) return { status: "bad", label: "Unhealthy" };
  if (s.kind === "manual") return { status: "ok", label: "Ready" };
  if (s.running) return { status: "ok", label: "Scanning" };
  return { status: "ok", label: "Healthy" };
}

function modeText(s: SourceHealth) {
  if (s.kind === "manual") return "Manual";
  return s.mode === "mock" ? "Mock data" : s.mode === "live" ? "Live" : s.mode;
}

const n = (v: number | null | undefined) => (v === null || v === undefined ? "—" : v.toLocaleString("nb-NO").replace(/ | /g, " "));

export default function SourcesPage() {
  const { data, error, loading, reload } = useApi<SourceHealth[]>("sources");
  const [runSource, setRunSource] = useState<"cardtrader" | "stores">("cardtrader");
  const finn = useApi<FinnSummary>("dashboard/finn");
  const runs = useApi<CollectorRun[]>(`sources/${runSource}/runs?limit=25`);
  const [msg, setMsg] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function runNow(source: string) {
    setActionError(null);
    setMsg(null);
    try {
      await api(`sources/${source}/run`, { method: "POST" });
      setMsg(`Scan of ${META[source]?.title ?? source} queued — results appear in a moment.`);
      setTimeout(() => {
        reload();
        runs.reload();
      }, 4000);
    } catch (e) {
      setActionError((e as Error).message);
    }
  }

  return (
    <>
      <PageHeader
        title="Sources"
        icon={RadioTower}
        subtitle="Where listings and prices come from, and how each collector is doing."
        actions={
          <button
            className={btn}
            onClick={() => {
              reload();
              runs.reload();
              finn.reload();
            }}
          >
            <RefreshCw size={14} /> Refresh
          </button>
        }
      />
      <ErrorBox error={error ?? actionError} />
      {msg && <div className="mb-4 rounded-xl border border-emerald-400/25 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">{msg}</div>}
      <Loading show={loading && !data} />

      {data && (
        <div className="grid gap-4 lg:grid-cols-3">
          {data.map((s) => {
            const meta = META[s.source] ?? { title: s.source, icon: RadioTower, blurb: "" };
            const st = status(s);
            const scheduled = s.kind === "scheduled";
            return (
              <StatusCard
                key={s.source}
                title={meta.title}
                icon={meta.icon}
                status={st.status}
                statusLabel={st.label}
                footer={
                  scheduled ? (
                    <button className={btn} disabled={!s.enabled || s.running} onClick={() => runNow(s.source)}>
                      <Play size={13} /> {s.running ? "Scan running…" : "Run now"}
                    </button>
                  ) : (
                    s.source === "finn" ? (
                    <Link href="/capture" className={btn}>
                      <MousePointerClick size={13} /> Capture a listing
                    </Link>
                  ) : (
                    <span className="text-xs text-ink-3">Add listings from the Deals page or the CLI.</span>
                  )
                  )
                }
              >
                <p className="mb-1.5 text-xs text-ink-3">{meta.blurb}</p>
                <Field label="Enabled" value={s.enabled ? "Yes" : "No"} />
                <Field label="Mode" value={modeText(s)} />
                {scheduled && <Field label="Interval" value={s.interval_minutes ? `every ${s.interval_minutes} min` : "—"} />}
                <Field label="Last success" value={s.last_success ? <span title={dt(s.last_success)}>{rel(s.last_success)}</span> : "—"} />
                <Field label="Last failure" value={s.last_failure ? <span title={dt(s.last_failure)}>{rel(s.last_failure)}</span> : "never"} />
                {scheduled && (
                  <>
                    <Field label="Next scan" value={<NextScan worker={s.worker} enabled={s.enabled} />} />
                    <LockRows lock={s.scan_lock} />
                    <Field label="Runs (24h)" value={s.runs_24h} />
                    <Field
                      label="Error rate (24h)"
                      value={<span className={s.error_rate_24h ? "text-loss" : ""}>{pct(s.error_rate_24h, 0)}</span>}
                    />
                    <Field label="Consecutive failures" value={s.consecutive_failures} />
                    <Field label="Last scan listings" value={`${n(s.last_items_fetched)} fetched · ${n(s.last_items_matched)} valid`} />
                    <Field label="Last duration" value={s.last_duration_ms !== null ? fmtSeconds(s.last_duration_ms / 1000) : "—"} />
                  </>
                )}
                {s.last_error && <p className="mt-2 break-words rounded-lg bg-loss/10 p-2 text-xs text-rose-200">{s.last_error}</p>}
              </StatusCard>
            );
          })}
        </div>
      )}

      {finn.data && (
        <Panel title="FINN" icon={Globe} className="mt-6" subtitle="User-driven discovery — what you have captured and how it scored">
          <FinnStatus data={finn.data} />
        </Panel>
      )}

      <Panel
        title="Recent runs"
        className="mt-6"
        bodyClassName="p-2 sm:p-3"
        actions={
          <Segmented
            value={runSource}
            onChange={setRunSource}
            options={[
              { value: "cardtrader", label: "CardTrader" },
              { value: "stores", label: "Web shops" },
            ]}
          />
        }
      >
        <ErrorBox error={runs.error} />
        <Loading show={runs.loading && !runs.data} />
        {runs.data && <RunsTable runs={runs.data} />}
      </Panel>
    </>
  );
}

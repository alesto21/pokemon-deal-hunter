"use client";

import {
  Activity,
  Archive,
  Bell,
  CheckCircle2,
  Database,
  Euro,
  Globe,
  RadioTower,
  RefreshCw,
  Store,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";
import RunsTable from "@/components/sources/RunsTable";
import JsonView from "@/components/system/JsonView";
import StatusCard, { type Status } from "@/components/system/StatusCard";
import TelegramTest from "@/components/system/TelegramTest";
import { fmtSeconds, LockRows, NextScan } from "@/components/system/WorkerRows";
import { Disclosure, ErrorBox, Field, Loading, PageHeader, Panel, btn } from "@/components/ui";
import { useApi } from "@/lib/api";
import type { SystemInfo } from "@/lib/dashboard";
import { bytes, day, dt, pct, rel } from "@/lib/format";
import type { CollectorRun, SourceHealth } from "@/lib/types";

function sourceStatus(s: SourceHealth | undefined): { status: Status; label: string } {
  if (!s || !s.enabled) return { status: "off", label: "Disabled" };
  if (s.worker?.next_scan_overdue) return { status: "bad", label: "Overdue" };
  if (s.healthy === false) return { status: "bad", label: "Errors" };
  if (s.kind === "manual") return { status: "ok", label: "Manual" };
  if (s.running) return { status: "ok", label: "Scanning" };
  return { status: "ok", label: "Healthy" };
}

function modeLabel(mode: string | null | undefined) {
  if (!mode) return "—";
  return mode === "mock" ? "Mock data" : mode === "live" ? "Live API" : mode === "dry-run" ? "Dry-run" : mode;
}

export default function SystemPage() {
  const { data, error, loading, reload } = useApi<SystemInfo>("dashboard/system");
  const runs = useApi<CollectorRun[]>("sources/cardtrader/runs?limit=10");

  const ct = data?.sources.find((s) => s.source === "cardtrader");
  const finn = data?.sources.find((s) => s.source === "finn");
  const stores = data?.sources.find((s) => s.source === "stores");
  const w = data?.worker;

  let workerStatus: { status: Status; label: string } = { status: "off", label: "Unknown" };
  if (w) {
    if (w.next_scan_overdue) workerStatus = { status: "bad", label: "Overdue" };
    else if (w.lock.locked && w.lock.stale) workerStatus = { status: "bad", label: "Stale lock" };
    else if (w.lock.locked) workerStatus = { status: "ok", label: "Scanning" };
    else if (w.worker_scheduled) workerStatus = { status: "ok", label: "Scheduled" };
    else workerStatus = { status: "warn", label: "Not scheduled" };
  }

  return (
    <>
      <PageHeader
        title="System"
        icon={Activity}
        subtitle="Scanner, worker, database and notification health."
        actions={
          <button
            className={btn}
            onClick={() => {
              reload();
              runs.reload();
            }}
          >
            <RefreshCw size={14} /> Refresh
          </button>
        }
      />
      <ErrorBox error={error} />
      <Loading show={loading && !data} />

      {data && (
        <div className="space-y-6">
          {/* Overall banner — a worker with no scan scheduled is not "operational" even if nothing is overdue */}
          {data.overall_ok && w && !w.worker_scheduled && !w.lock.locked ? (
            <div className="flex items-center gap-3 rounded-xl border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm">
              <TriangleAlert size={18} className="shrink-0 text-warn" />
              <div>
                <div className="font-medium text-ink">Worker not running</div>
                <div className="text-xs text-ink-2">
                  No scan is scheduled, so prices and deals are not being refreshed. Last scan {rel(w.last_successful_scan)}. Start it with{" "}
                  <code className="text-ink">docker compose up -d worker</code>.
                </div>
              </div>
            </div>
          ) : data.overall_ok ? (
            <div className="flex items-center gap-3 rounded-xl border border-emerald-400/25 bg-emerald-500/10 px-4 py-3 text-sm">
              <CheckCircle2 size={18} className="shrink-0 text-gain" />
              <div>
                <div className="font-medium text-ink">All systems operational</div>
                <div className="text-xs text-ink-2">
                  Last scan {rel(w?.last_successful_scan)} · next {w?.next_scheduled_scan ? rel(w.next_scheduled_scan) : "not scheduled"}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3 rounded-xl border border-loss/40 bg-loss/10 px-4 py-3 text-sm">
              <TriangleAlert size={18} className="shrink-0 text-loss" />
              <div>
                <div className="font-medium text-ink">Attention needed</div>
                <div className="text-xs text-ink-2">
                  {w?.next_scan_overdue
                    ? "The worker's next scan is overdue — the worker is probably not running."
                    : !data.database.ok
                      ? "The database is not reachable."
                      : data.database.migrations !== "ok"
                        ? "Database migrations are pending."
                        : "One or more checks failed — see details below."}
                </div>
              </div>
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {/* Worker */}
            <StatusCard title="Worker" icon={Activity} status={workerStatus.status} statusLabel={workerStatus.label}>
              {w ? (
                <>
                  <Field label="Next scan" value={<NextScan worker={w} />} />
                  <Field label="Last successful scan" value={w.last_successful_scan ? rel(w.last_successful_scan) : "—"} />
                  <Field label="Interval" value={w.interval_minutes ? `${w.interval_minutes} min` : "—"} />
                  <Field label="Scans (24h)" value={w.scans_24h} />
                  <Field
                    label="Errors (24h)"
                    value={
                      <span className={w.errors_24h ? "text-loss" : ""}>
                        {w.errors_24h} · {pct(w.error_rate_24h, 0)}
                      </span>
                    }
                  />
                  <LockRows lock={w.lock} showOwner={false} />
                  {w.last_error && <p className="mt-2 break-words rounded-lg bg-loss/10 p-2 text-xs text-rose-200">{w.last_error}</p>}
                </>
              ) : (
                <p className="py-2 text-sm text-ink-3">No scheduled scanner configured.</p>
              )}
            </StatusCard>

            {/* CardTrader */}
            <StatusCard
              title="CardTrader"
              icon={RadioTower}
              status={sourceStatus(ct).status}
              statusLabel={sourceStatus(ct).label}
              footer={
                <Link href="/sources" className="text-xs text-ink-3 hover:text-ink">
                  Source details →
                </Link>
              }
            >
              <Field label="Mode" value={modeLabel(data.cardtrader.mode)} />
              <Field label="Last success" value={ct?.last_success ? rel(ct.last_success) : "—"} />
              <Field label="Last failure" value={ct?.last_failure ? rel(ct.last_failure) : "never"} />
              <Field label="Error rate (24h)" value={pct(ct?.error_rate_24h, 0)} />
              <Field
                label="Last scan"
                value={
                  ct?.last_items_fetched !== null && ct?.last_items_fetched !== undefined
                    ? `${ct.last_items_fetched.toLocaleString("nb-NO")} listings · ${fmtSeconds((ct.last_duration_ms ?? 0) / 1000)}`
                    : "—"
                }
              />
            </StatusCard>

            {/* Database */}
            <StatusCard
              title="Database"
              icon={Database}
              status={data.database.ok ? (data.database.migrations === "ok" ? "ok" : "warn") : "bad"}
              statusLabel={data.database.ok ? (data.database.migrations === "ok" ? "Healthy" : "Migrations pending") : "Unreachable"}
            >
              <Field label="Engine" value={data.database.dialect === "postgresql" ? "PostgreSQL" : data.database.dialect} />
              <Field label="Schema version" value={data.database.migration_version ?? "—"} />
              <Field label="Size" value={bytes(data.database.size_bytes)} />
            </StatusCard>

            {/* Telegram */}
            <StatusCard
              title="Telegram"
              icon={Bell}
              status={data.telegram.mode === "live" ? "ok" : "warn"}
              statusLabel={data.telegram.mode === "live" ? "Live" : "Dry-run"}
              footer={<TelegramTest dryRun={data.telegram.mode !== "live"} />}
            >
              <Field label="Mode" value={data.telegram.mode === "live" ? "Alerts are sent" : "Alerts are only logged"} />
              <Field label="Bot + chat configured" value={data.telegram.configured ? "Yes" : "No"} />
              <Field label="Last deal alert" value={data.telegram.last_deal_alert_at ? rel(data.telegram.last_deal_alert_at) : "—"} />
            </StatusCard>

            {/* FINN */}
            <StatusCard title="FINN" icon={Globe} status={sourceStatus(finn).status} statusLabel={finn?.enabled ? "Manual" : "Disabled"}>
              <Field label="Ingestion" value="Pasted URLs / CSV import" />
              <Field label="Automated crawling" value="Never" />
              <Field label="Last run" value={finn?.last_success ? rel(finn.last_success) : "—"} />
            </StatusCard>

            {/* Stores */}
            <StatusCard title="Web shops" icon={Store} status={sourceStatus(stores).status} statusLabel={sourceStatus(stores).label}>
              <Field label="Adapter" value="Shopify (opt-in)" />
              <Field label="Enabled" value={stores?.enabled ? "Yes" : "No"} />
              <Field label="Last success" value={stores?.last_success ? rel(stores.last_success) : "—"} />
            </StatusCard>

            {/* Backups */}
            <StatusCard
              title="Backups"
              icon={Archive}
              status={data.backups.configured ? (data.backups.latest_at ? "ok" : "warn") : "off"}
              statusLabel={data.backups.configured ? (data.backups.latest_at ? "Configured" : "No backups yet") : "Not configured"}
            >
              {data.backups.configured ? (
                <>
                  <Field label="Latest" value={data.backups.latest_at ? rel(data.backups.latest_at) : "—"} />
                  <Field label="Size" value={bytes(data.backups.latest_size_bytes)} />
                  <Field label="Kept" value={`${data.backups.count_daily} daily · ${data.backups.count_weekly} weekly`} />
                </>
              ) : (
                <p className="py-1 text-sm text-ink-3">
                  Backup status is available in production (the backup container writes to <code className="text-ink-2">./backups</code>).
                </p>
              )}
            </StatusCard>

            {/* FX */}
            <StatusCard title="Exchange rate" icon={Euro} status={data.fx.eur_nok ? "ok" : "warn"} statusLabel={data.fx.eur_nok ? "Current" : "Fallback"}>
              <Field label="EUR → NOK" value={data.fx.eur_nok ? data.fx.eur_nok.toFixed(4) : "—"} />
              <Field label="As of" value={day(data.fx.day)} />
              <Field label="Source" value="ECB (Frankfurter), daily" />
            </StatusCard>
          </div>

          <Panel title="Recent scans" bodyClassName="p-2 sm:p-3">
            <ErrorBox error={runs.error} />
            {runs.data && <RunsTable runs={runs.data} />}
          </Panel>

          <Disclosure title="Diagnostics">
            <div className="space-y-4 text-sm">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <div className="mb-1 text-xs font-medium uppercase tracking-wider text-ink-3">Readiness checks</div>
                  {Object.entries(data.diagnostics.ready_checks).map(([k, v]) => (
                    <Field key={k} label={k} value={<span className={v === "ok" || !["database", "migrations", "config"].includes(k) ? "" : "text-loss"}>{v}</span>} />
                  ))}
                  <Field label="environment" value={data.diagnostics.environment} />
                  <Field label="schema version" value={data.database.migration_version ?? "—"} />
                </div>
                {w && (
                  <div>
                    <div className="mb-1 text-xs font-medium uppercase tracking-wider text-ink-3">Scan lock & schedule</div>
                    <LockRows lock={w.lock} />
                    <Field label="Lock acquired" value={dt(w.lock.acquired_at)} />
                    <Field label="Heartbeat at" value={dt(w.lock.heartbeat_at)} />
                    <Field label="Next scan (stored)" value={dt(w.next_scheduled_scan)} />
                    <Field label="Overdue by" value={w.next_scan_overdue ? fmtSeconds(w.next_scan_overdue_seconds) : "—"} />
                  </div>
                )}
              </div>
              <div>
                <div className="mb-1 text-xs font-medium uppercase tracking-wider text-ink-3">Raw status</div>
                <JsonView value={{ database: data.database, worker: data.worker, diagnostics: data.diagnostics }} />
              </div>
            </div>
          </Disclosure>
        </div>
      )}
    </>
  );
}

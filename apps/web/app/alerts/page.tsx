"use client";

import { Bell, BellOff, ExternalLink, HeartPulse, RefreshCw } from "lucide-react";
import { useState } from "react";
import { EntityCell } from "@/components/alerts/EntityCell";
import { Badge, DataTable, EmptyState, ErrorBox, KpiCard, LevelBadge, Loading, PageHeader, Panel, Segmented, btn } from "@/components/ui";
import { useApi } from "@/lib/api";
import type { AlertRow, Alerts, BlockedRow } from "@/lib/dashboard";
import { dt, nok, pct } from "@/lib/format";

function Delivery({ a }: { a: AlertRow }) {
  if (a.dry_run) return <Badge tone="warn" title="Telegram is in dry-run mode: the alert was logged, not sent">Dry-run</Badge>;
  if (a.delivered) return <Badge tone="gain" title={`Telegram message ${a.telegram_message_id}`}>Sent</Badge>;
  return <Badge tone="loss" title="Live mode, but Telegram did not confirm delivery">Not delivered</Badge>;
}

function OpenLink({ url }: { url: string | null }) {
  if (!url) return null;
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} className="inline-flex items-center gap-1 text-xs text-ink-3 hover:text-ink">
      Open <ExternalLink size={12} />
    </a>
  );
}

/** Turn backend block reasons into short, readable labels. */
function reasonLabel(r: string): string {
  if (r.startsWith("seller_region_not_allowed")) return r.replace("seller_region_not_allowed", "Seller region not allowed");
  if (r.startsWith("already alerted")) return "Already alerted (cooldown)";
  if (r.startsWith("same card alerted recently")) return "Same card alerted recently";
  if (r.startsWith("daily alert cap")) return r.replace("daily alert cap", "Daily cap");
  // Older evaluations stored the capped level as "recommendation WATCH"
  if (/^recommendation (WATCH|IGNORE)$/.test(r)) return `Discount only supported ${r.split(" ")[1]}`;
  return r.charAt(0).toUpperCase() + r.slice(1);
}

function DealAlerts({ rows }: { rows: AlertRow[] }) {
  return (
    <DataTable
      rows={rows}
      rowKey={(a) => a.id}
      empty={<EmptyState icon={Bell} title="No deal alerts in this period">Alerts appear here when a deal passes every filter.</EmptyState>}
      columns={[
        { key: "time", header: "Time", cell: (a) => <span className="whitespace-nowrap text-ink-2">{dt(a.sent_at)}</span> },
        { key: "card", header: "Card", cell: (a) => <EntityCell entity={a.entity} fallback={a.title} /> },
        { key: "source", header: "Source", cell: (a) => <span className="text-ink-2">{a.source ?? "—"}</span>, hideBelow: "lg" },
        { key: "level", header: "Level", cell: (a) => <LevelBadge level={a.level} /> },
        { key: "price", header: "Landed", align: "right", cell: (a) => <span className="whitespace-nowrap">{nok(a.price_nok)}</span> },
        { key: "fv", header: "Fair value", align: "right", cell: (a) => <span className="whitespace-nowrap">{nok(a.fair_value_nok)}</span>, hideBelow: "lg" },
        { key: "disc", header: "Discount", align: "right", cell: (a) => <span className="text-gain">{pct(a.discount_pct)}</span> },
        { key: "delivery", header: "Delivery", cell: (a) => <Delivery a={a} /> },
        { key: "link", header: "", align: "right", cell: (a) => <OpenLink url={a.url} /> },
      ]}
      mobileCard={(a) => (
        <div className="space-y-2">
          <div className="flex items-start justify-between gap-2">
            <EntityCell entity={a.entity} fallback={a.title} />
            <LevelBadge level={a.level} />
          </div>
          <div className="num flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-2">
            <span>{nok(a.price_nok)}</span>
            <span className="text-ink-3">fv {nok(a.fair_value_nok)}</span>
            <span className="text-gain">{pct(a.discount_pct)}</span>
          </div>
          <div className="flex items-center justify-between gap-2 text-xs text-ink-3">
            <span>
              {dt(a.sent_at)} · {a.source}
            </span>
            <span className="flex items-center gap-3">
              <Delivery a={a} />
              <OpenLink url={a.url} />
            </span>
          </div>
        </div>
      )}
    />
  );
}

function Blocked({ rows }: { rows: BlockedRow[] }) {
  const reasons = (b: BlockedRow) => (
    <div className="flex flex-wrap gap-1">
      {b.cooldown && <Badge tone="info">Cooldown</Badge>}
      {b.region_blocked && <Badge tone="warn">Region</Badge>}
      {b.blocked_by
        .filter((r) => !(b.region_blocked && r.startsWith("seller_region_not_allowed")))
        .filter((r) => !(b.cooldown && (r.startsWith("already alerted") || r.startsWith("same card alerted recently"))))
        .map((r) => (
          <Badge key={r} title={r}>
            {reasonLabel(r)}
          </Badge>
        ))}
    </div>
  );
  return (
    <DataTable
      rows={rows}
      rowKey={(b) => b.evaluation_id}
      empty={<EmptyState icon={BellOff} title="Nothing was held back">Every GOOD-or-better evaluation in this period either alerted or had no decision recorded.</EmptyState>}
      columns={[
        { key: "time", header: "Evaluated", cell: (b) => <span className="whitespace-nowrap text-ink-2">{dt(b.timestamp)}</span> },
        { key: "card", header: "Card", cell: (b) => <EntityCell entity={b.entity} fallback={b.title} /> },
        { key: "level", header: "Level", cell: (b) => <LevelBadge level={b.level} /> },
        { key: "price", header: "Landed", align: "right", cell: (b) => <span className="whitespace-nowrap">{nok(b.price_nok)}</span>, hideBelow: "lg" },
        { key: "disc", header: "Discount", align: "right", cell: (b) => pct(b.discount_pct) },
        { key: "why", header: "Why not sent", cell: reasons },
        { key: "link", header: "", align: "right", cell: (b) => <OpenLink url={b.url} /> },
      ]}
      mobileCard={(b) => (
        <div className="space-y-2">
          <div className="flex items-start justify-between gap-2">
            <EntityCell entity={b.entity} fallback={b.title} />
            <LevelBadge level={b.level} />
          </div>
          <div className="num flex flex-wrap gap-x-3 text-xs text-ink-2">
            <span>{nok(b.price_nok)}</span>
            <span>{pct(b.discount_pct)}</span>
            <span className="text-ink-3">{dt(b.timestamp)}</span>
          </div>
          {reasons(b)}
        </div>
      )}
    />
  );
}

function HealthAlerts({ rows }: { rows: AlertRow[] }) {
  return (
    <ul className="divide-y divide-line">
      {rows.map((a) => (
        <li key={a.id} className="flex flex-col gap-1 py-2.5 sm:flex-row sm:items-start sm:gap-4">
          <span className="shrink-0 text-xs text-ink-3 sm:w-36">{dt(a.sent_at)}</span>
          <span className="min-w-0 flex-1 break-words text-sm text-ink-2">{(a.message ?? "").replace(/<[^>]+>/g, "")}</span>
          <span className="shrink-0">{a.dry_run ? <Badge tone="warn">Dry-run</Badge> : <Badge>{a.delivered ? "Sent" : "Logged"}</Badge>}</span>
        </li>
      ))}
    </ul>
  );
}

export default function AlertsPage() {
  const [days, setDays] = useState<"7" | "30">("7");
  const { data, error, loading, reload } = useApi<Alerts>(`dashboard/alerts?days=${days}`);
  const deal = data?.alerts.filter((a) => a.kind === "deal") ?? [];
  const health = data?.alerts.filter((a) => a.kind !== "deal") ?? [];
  const s = data?.summary;

  return (
    <>
      <PageHeader
        title="Alerts"
        icon={Bell}
        subtitle="What was alerted, and what was held back and why."
        actions={
          <>
            <Segmented
              value={days}
              onChange={setDays}
              options={[
                { value: "7", label: "7 days" },
                { value: "30", label: "30 days" },
              ]}
            />
            <button className={btn} onClick={reload}>
              <RefreshCw size={14} /> Refresh
            </button>
          </>
        }
      />
      <ErrorBox error={error} />
      <Loading show={loading && !data} />

      {data && s && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            <KpiCard label="Today" value={s.today} />
            <KpiCard label={`Last ${s.window_days} days`} value={s.window} />
            <KpiCard label="Steal" value={s.by_level.STEAL} />
            <KpiCard label="Strong buy" value={s.by_level.STRONG_BUY} />
            <KpiCard label="Good" value={s.by_level.GOOD} />
            <KpiCard label="Live / dry-run" value={`${s.live} / ${s.dry_run}`} hint={s.dry_run && !s.live ? "Telegram in dry-run" : undefined} />
            <KpiCard label="Held back" value={s.blocked} hint="GOOD+ not sent" />
          </div>

          <Panel title="Deal alerts" subtitle="Level shown is the effective alert level after caps." bodyClassName="p-2 sm:p-3">
            <DealAlerts rows={deal} />
          </Panel>

          <Panel title="Held back" subtitle="GOOD-or-better evaluations that did not alert — cooldowns, daily cap, seller region, hard filters." bodyClassName="p-2 sm:p-3">
            <Blocked rows={data.blocked} />
          </Panel>

          {health.length > 0 && (
            <Panel title="System notifications" icon={HeartPulse} subtitle="Source-health, digest and test messages.">
              <HealthAlerts rows={health} />
            </Panel>
          )}
        </div>
      )}
    </>
  );
}

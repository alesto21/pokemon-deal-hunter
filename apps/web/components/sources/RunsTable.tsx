"use client";

import { CheckCircle2, XCircle } from "lucide-react";
import { DataTable, EmptyState } from "@/components/ui";
import { dt } from "@/lib/format";
import type { CollectorRun } from "@/lib/types";

const dur = (ms: number | null) => (ms === null ? "—" : `${(ms / 1000).toFixed(1)} s`);
const n = (v: number) => v.toLocaleString("nb-NO").replace(/ | /g, " ");

function Result({ ok }: { ok: boolean }) {
  return ok ? (
    <span className="inline-flex items-center gap-1 text-gain">
      <CheckCircle2 size={14} /> ok
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-loss">
      <XCircle size={14} /> failed
    </span>
  );
}

export default function RunsTable({ runs }: { runs: CollectorRun[] }) {
  return (
    <DataTable
      rows={runs}
      rowKey={(r) => r.id}
      empty={<EmptyState title="No runs recorded yet" />}
      columns={[
        { key: "started", header: "Started", cell: (r) => <span className="whitespace-nowrap">{dt(r.started_at)}</span> },
        { key: "source", header: "Source", cell: (r) => r.source, hideBelow: "lg" },
        { key: "result", header: "Result", cell: (r) => <Result ok={r.success} /> },
        { key: "duration", header: "Duration", align: "right", cell: (r) => dur(r.duration_ms) },
        { key: "fetched", header: "Fetched", align: "right", cell: (r) => n(r.items_fetched) },
        { key: "matched", header: "Valid", align: "right", cell: (r) => n(r.items_matched), hideBelow: "lg" },
        { key: "eval", header: "Evaluated", align: "right", cell: (r) => n(r.listings_evaluated), hideBelow: "lg" },
        { key: "deals", header: "Deals", align: "right", cell: (r) => r.deals_found },
        { key: "alerts", header: "Alerts", align: "right", cell: (r) => r.alerts_sent },
        {
          key: "notes",
          header: "Notes",
          hideBelow: "xl",
          cell: (r) => <span className="line-clamp-2 max-w-xs break-words text-xs text-ink-3">{r.error ?? ""}</span>,
        },
      ]}
      mobileCard={(r) => (
        <div className="space-y-1 text-sm">
          <div className="flex items-center justify-between gap-2">
            <span className="text-ink-2">{dt(r.started_at)}</span>
            <Result ok={r.success} />
          </div>
          <div className="num flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-ink-3">
            <span>{dur(r.duration_ms)}</span>
            <span>{n(r.items_fetched)} fetched</span>
            <span>{n(r.items_matched)} valid</span>
            <span>{r.deals_found} deals</span>
            <span>{r.alerts_sent} alerts</span>
          </div>
          {r.error && <div className="break-words text-xs text-ink-3">{r.error}</div>}
        </div>
      )}
    />
  );
}

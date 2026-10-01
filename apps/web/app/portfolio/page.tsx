"use client";

import { Plus, RefreshCw, Search, Wallet } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { entityName, entitySub, GradingBadge, KindBadge, UnpricedNote } from "@/components/portfolio/common";
import { AddHoldingForm, EditHoldingDrawer } from "@/components/portfolio/HoldingForms";
import { AllocationBars, CostValueBars, PnlHistoryChart, ValueHistoryChart } from "@/components/portfolio/PortfolioCharts";
import { KindBreakdown, PortfolioKpis } from "@/components/portfolio/PortfolioKpis";
import {
  btnGhost,
  btnPrimary,
  CardThumb,
  type Column,
  DataTable,
  Delta,
  EmptyState,
  ErrorBox,
  input,
  Loading,
  PageHeader,
  Panel,
  Segmented,
} from "@/components/ui";
import { useApi } from "@/lib/api";
import type { HoldingRow, PortfolioPage } from "@/lib/dashboard";
import { day, nok } from "@/lib/format";


const BINDER_LABEL: Record<string, string> = { premium: "GOD binder", regular: "Collection", graded: "Graded", sealed: "Sealed" };

const COLUMNS: Column<HoldingRow>[] = [
  {
    key: "item",
    header: "Holding",
    cell: (h) => (
      <div className="flex items-center gap-3">
        <CardThumb src={h.entity?.image_url} alt={h.entity?.name ?? ""} size="sm" />
        <div className="min-w-0">
          <div className="truncate text-ink">
            {entityName(h.entity)}
            {h.quantity > 1 && <span className="ml-1 text-ink-3">×{h.quantity}</span>}
          </div>
          <div className="truncate text-xs text-ink-3">{entitySub(h.entity)}</div>
        </div>
      </div>
    ),
  },
  {
    key: "type",
    header: "Type",
    hideBelow: "lg",
    cell: (h) => (
      <div className="flex flex-wrap gap-1">
        <KindBadge kind={h.kind} />
        {h.kind !== "sealed" && h.grading_status !== "raw" && <GradingBadge status={h.grading_status} company={h.grade_company} grade={h.grade} />}
      </div>
    ),
  },
  { key: "binder", header: "Binder", hideBelow: "xl", cell: (h) => <span className="text-ink-2">{BINDER_LABEL[h.binder_type] ?? h.binder_type}</span> },
  { key: "cost", header: "Cost", align: "right", cell: (h) => nok(h.cost_nok) },
  { key: "value", header: "Market value", align: "right", cell: (h) => (h.value_priced ? nok(h.value_nok) : <span className="text-ink-3">No price</span>) },
  { key: "pl", header: "P/L", align: "right", cell: (h) => <Delta nokValue={h.gain_nok} pctValue={h.gain_pct} /> },
  { key: "date", header: "Bought", align: "right", hideBelow: "xl", cell: (h) => <span className="text-ink-3">{day(h.acquisition_date)}</span> },
];

function mobileCard(h: HoldingRow) {
  return (
    <div className="flex items-center gap-3">
      <CardThumb src={h.entity?.image_url} alt={h.entity?.name ?? ""} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm text-ink">
          {entityName(h.entity)}
          {h.quantity > 1 && <span className="ml-1 text-ink-3">×{h.quantity}</span>}
        </div>
        <div className="mt-1 flex flex-wrap gap-1">
          <KindBadge kind={h.kind} />
          {h.kind !== "sealed" && h.grading_status !== "raw" && <GradingBadge status={h.grading_status} company={h.grade_company} grade={h.grade} />}
        </div>
      </div>
      <div className="shrink-0 text-right text-xs">
        <div className="num text-sm text-ink">{h.value_priced ? nok(h.value_nok) : "No price"}</div>
        <div className="num text-ink-3">cost {nok(h.cost_nok)}</div>
        <Delta pctValue={h.gain_pct} />
      </div>
    </div>
  );
}

type Kind = "all" | "raw" | "graded" | "sealed";
type Sort = "value" | "gain" | "cost" | "name" | "date";

function PortfolioPageInner() {
  const params = useSearchParams();
  const overview = useApi<PortfolioPage>("dashboard/portfolio");
  const [adding, setAdding] = useState(params.get("add") === "1");
  const [editing, setEditing] = useState<HoldingRow | null>(null);
  const [kind, setKind] = useState<Kind>("all");
  const [sort, setSort] = useState<Sort>("value");
  const [binder, setBinder] = useState("");
  const [q, setQ] = useState("");

  const reload = overview.reload;
  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const sorters: Record<Sort, (a: HoldingRow, b: HoldingRow) => number> = {
      value: (a, b) => b.value_nok - a.value_nok,
      gain: (a, b) => (b.gain_pct ?? -Infinity) - (a.gain_pct ?? -Infinity),
      cost: (a, b) => b.cost_nok - a.cost_nok,
      name: (a, b) => (a.entity?.name ?? "").localeCompare(b.entity?.name ?? ""),
      date: (a, b) => (b.acquisition_date ?? b.added_at).localeCompare(a.acquisition_date ?? a.added_at),
    };
    return (overview.data?.holdings ?? [])
      .filter((h) => kind === "all" || h.kind === kind)
      .filter((h) => !binder || h.binder_type === binder)
      .filter((h) => !needle || `${h.entity?.name} ${h.entity?.number ?? ""} ${h.entity?.set_name ?? ""}`.toLowerCase().includes(needle))
      .sort(sorters[sort]);
  }, [overview.data, kind, binder, q, sort]);

  const p = overview.data;
  const hasHoldings = (p?.summary.item_count ?? 0) > 0;
  const unpriced = p ? p.by_kind.raw.unpriced + p.by_kind.graded.unpriced + p.by_kind.sealed.unpriced : 0;
  const loading = overview.loading;

  return (
    <>
      <PageHeader
        title="Portfolio"
        icon={Wallet}
        subtitle="Everything you own — valued at live fair value, graded cards at your PSA references"
        actions={
          <>
            <button className={btnGhost} onClick={reload} disabled={loading}>
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
            </button>
            <button className={btnPrimary} onClick={() => setAdding((a) => !a)}>
              <Plus size={15} /> Add holding
            </button>
          </>
        }
      />
      <ErrorBox error={overview.error} />
      {adding && (
        <Panel title="Add a holding" className="mb-6">
          <AddHoldingForm onDone={() => { setAdding(false); reload(); }} onCancel={() => setAdding(false)} />
        </Panel>
      )}
      <Loading show={loading && !p} />
      {p && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <PortfolioKpis p={p} />
          </div>
          {hasHoldings && <KindBreakdown byKind={p.by_kind} />}
          <UnpricedNote count={unpriced} />

          {!hasHoldings ? (
            !adding && (
              <Panel>
                <EmptyState icon={Wallet} title="No holdings yet"
                  action={<button className={btnPrimary} onClick={() => setAdding(true)}><Plus size={15} /> Add your first card</button>}>
                  Search any card or sealed product from the tracked sets, enter what you paid, and pick a binder.
                  Market values come from live CardTrader prices.
                </EmptyState>
              </Panel>
            )
          ) : (
            <>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                <Panel title="Portfolio value" subtitle="Market value vs cost basis, daily snapshots" className="lg:col-span-2">
                  <ValueHistoryChart history={p.history} />
                </Panel>
                <Panel title="Allocation" subtitle="Share of current market value">
                  <AllocationBars allocation={p.allocation} />
                </Panel>
              </div>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <Panel title="Cost vs market value" subtitle="Per holding type, today">
                  <CostValueBars byKind={p.by_kind} />
                </Panel>
                <Panel title="Unrealised profit / loss" subtitle="Daily snapshots">
                  <PnlHistoryChart history={p.history} />
                </Panel>
              </div>
              <Panel
                title={`Holdings · ${rows.length}`}
                subtitle="Click a holding to edit or remove it"
                actions={
                  <Segmented<Kind>
                    value={kind}
                    onChange={setKind}
                    options={[
                      { value: "all", label: "All" },
                      { value: "raw", label: "Raw" },
                      { value: "graded", label: "Graded" },
                      { value: "sealed", label: "Sealed" },
                    ]}
                  />
                }
              >
                <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-4">
                  <div className="relative col-span-2">
                    <Search size={14} className="pointer-events-none absolute left-2.5 top-2.5 text-ink-3" />
                    <input className={`${input} pl-8`} placeholder="Search holdings…" value={q} onChange={(e) => setQ(e.target.value)} />
                  </div>
                  <select className={input} value={binder} onChange={(e) => setBinder(e.target.value)} aria-label="Binder">
                    <option value="">All binders</option>
                    {Object.entries(BINDER_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                  <select className={input} value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label="Sort">
                    <option value="value">Sort: market value</option>
                    <option value="gain">Sort: gain %</option>
                    <option value="cost">Sort: cost</option>
                    <option value="name">Sort: name</option>
                    <option value="date">Sort: purchase date</option>
                  </select>
                </div>
                <DataTable rows={rows} columns={COLUMNS} rowKey={(h) => h.id} mobileCard={mobileCard} onRowClick={setEditing}
                  empty={<EmptyState title="No holdings match" />} />
              </Panel>
            </>
          )}
        </div>
      )}
      {editing && <EditHoldingDrawer h={editing} onClose={() => setEditing(null)} onSaved={reload} />}
    </>
  );
}

export default function PortfolioPage() {
  return (
    <Suspense fallback={<Loading />}>
      <PortfolioPageInner />
    </Suspense>
  );
}

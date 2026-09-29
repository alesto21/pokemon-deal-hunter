"use client";

import { useState } from "react";
import AddPortfolioItem from "@/components/AddPortfolioItem";
import { PortfolioChart } from "@/components/Charts";
import HoldingsTable from "@/components/HoldingsTable";
import { Empty, ErrorBox, Loading, PageHeader, Panel, StatTile, btn } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { gainClass, nok, pct } from "@/lib/format";
import type { Holding, PortfolioSummary } from "@/lib/types";

export default function PortfolioPage() {
  const summary = useApi<PortfolioSummary>("portfolio/summary");
  const holdings = useApi<Holding[]>("portfolio");
  const [showAdd, setShowAdd] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const s = summary.data;

  const reload = () => {
    summary.reload();
    holdings.reload();
  };

  async function del(id: number) {
    if (!confirm("Delete this portfolio item?")) return;
    try {
      await api(`portfolio/${id}`, { method: "DELETE" });
      reload();
    } catch (e) {
      setActionError((e as Error).message);
    }
  }

  return (
    <>
      <PageHeader
        title="Portfolio"
        subtitle="Values use conservative fair values (raw) or your graded references (graded items)."
        actions={<button className={btn} onClick={() => setShowAdd((x) => !x)}>{showAdd ? "Hide form" : "+ Add item"}</button>}
      />
      <ErrorBox error={summary.error ?? holdings.error ?? actionError} />
      {showAdd && (
        <Panel title="Add portfolio item" className="mb-6">
          <AddPortfolioItem onDone={reload} />
        </Panel>
      )}
      <Loading show={summary.loading && !s} />
      {s && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <StatTile label="Total spent" value={nok(s.total_cost_nok)} hint={`${s.item_count} items`} />
            <StatTile label="Raw value" value={nok(s.raw_value_nok)} />
            <StatTile label="Graded value" value={nok(s.graded_value_nok)} />
            <StatTile label="Unrealized" value={nok(s.unrealized_gain_nok)} hint={pct(s.unrealized_gain_pct, 1, true)} className={gainClass(s.unrealized_gain_nok)} />
            <StatTile label="30-day change" value={s.change_30d_nok === null ? "—" : nok(s.change_30d_nok)} className={gainClass(s.change_30d_nok)} />
          </div>
          <div className="grid gap-6 lg:grid-cols-3">
            <Panel title="Value history" className="lg:col-span-2">
              {s.history.length > 1 ? <PortfolioChart history={s.history} /> : <Empty>Daily portfolio snapshots will build this chart over time.</Empty>}
            </Panel>
            <Panel title="Binder value by category">
              {Object.keys(s.by_binder).length === 0 ? (
                <Empty>No items.</Empty>
              ) : (
                <ul className="space-y-2 text-sm">
                  {Object.entries(s.by_binder).map(([k, v]) => (
                    <li key={k} className="flex justify-between">
                      <span className="capitalize">{k}</span>
                      <span className="tabular-nums">{nok(v)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="Top 10 holdings"><HoldingsTable items={s.top_holdings} compact /></Panel>
            <Panel title="Recent purchases"><HoldingsTable items={s.recent_purchases} compact /></Panel>
            <Panel title="Best performers"><HoldingsTable items={s.best_performers} compact /></Panel>
            <Panel title="Worst performers"><HoldingsTable items={s.worst_performers} compact /></Panel>
          </div>
        </div>
      )}
      <Panel title="All holdings" className="mt-6">
        <Loading show={holdings.loading && !holdings.data} />
        {holdings.data && <HoldingsTable items={holdings.data} onDelete={del} />}
      </Panel>
    </>
  );
}

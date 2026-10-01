"use client";

import { Bell, Eye, Globe, LayoutDashboard, RefreshCw, Tag, Wallet } from "lucide-react";
import Link from "next/link";
import { BestDeals } from "@/components/overview/BestDeals";
import { SystemStrip } from "@/components/overview/SystemStrip";
import { AddFirstCta, HoldingList } from "@/components/portfolio/common";
import { AllocationBars, CostValueBars, PnlHistoryChart, ValueHistoryChart } from "@/components/portfolio/PortfolioCharts";
import { KindBreakdown, PortfolioKpis } from "@/components/portfolio/PortfolioKpis";
import { btnGhost, EmptyState, ErrorBox, KpiCard, Loading, PageHeader, Panel } from "@/components/ui";
import { useApi } from "@/lib/api";
import { day } from "@/lib/format";
import type { FinnSummary, Overview } from "@/lib/dashboard";
import { FinnStatus } from "@/components/finn/FinnStatus";

export default function OverviewPage() {
  const { data, error, loading, reload } = useApi<Overview>("dashboard/overview");
  const finn = useApi<FinnSummary>("dashboard/finn");
  const p = data?.portfolio;
  const hasHoldings = (p?.summary.item_count ?? 0) > 0;

  return (
    <>
      <PageHeader
        title="Overview"
        icon={LayoutDashboard}
        subtitle="Your collection, live deals and the scanner at a glance"
        actions={
          <button className={btnGhost} onClick={() => { reload(); finn.reload(); }} disabled={loading}>
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        }
      />
      <ErrorBox error={error} />
      <Loading show={loading && !data} />
      {data && p && (
        <div className="space-y-6">
          {/* KPIs — portfolio first, then activity */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <PortfolioKpis p={p} compact />
            <KpiCard label="Active deals" icon={Tag} tone={data.kpis.active_deals ? "gold" : null} value={data.kpis.active_deals}
              hint={`GOOD or better · ${data.kpis.active_listings} listings tracked`} />
            <KpiCard label="Watchlist" icon={Eye} value={data.kpis.watchlist_count} hint="enabled targets" />
            <KpiCard label="Alerts today" icon={Bell} value={data.kpis.alerts_today.total}
              hint={`${data.kpis.alerts_today.live} live · ${data.kpis.alerts_today.dry_run} dry-run`} />
            <KpiCard label="Portfolio items" icon={Wallet} value={p.summary.item_count}
              hint={`${p.by_kind.raw.count} raw · ${p.by_kind.graded.count} graded · ${p.by_kind.sealed.count} sealed`} />
          </div>
          {hasHoldings && <KindBreakdown byKind={p.by_kind} />}
          <SystemStrip system={data.system} />

          <Panel
            title="Best deals right now"
            icon={Tag}
            subtitle="Effective level after caps · landed cost = item + shipping + import buffer"
            actions={<Link href="/deals" className="text-xs text-ink-3 hover:text-ink">All deals →</Link>}
          >
            <BestDeals best={data.best_deals} near={data.near_deals} />
          </Panel>

          {finn.data && (
            <Panel title="FINN" icon={Globe} subtitle="Listings you captured from FINN"
              actions={<Link href="/capture" className="text-xs text-ink-3 hover:text-ink">Capture →</Link>}>
              <FinnStatus data={finn.data} compact />
            </Panel>
          )}

          {hasHoldings ? (
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
                <Panel title="Cost vs market value" subtitle="What you paid vs what it is worth today">
                  <CostValueBars byKind={p.by_kind} />
                </Panel>
                <Panel title="Unrealised profit / loss" subtitle="Daily snapshots">
                  <PnlHistoryChart history={p.history} />
                </Panel>
              </div>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <Panel title="Top performers" bodyClassName="px-4 py-1">
                  <HoldingList rows={p.top_performers} empty="No holding is in profit yet." />
                </Panel>
                <Panel title="Largest positions" bodyClassName="px-4 py-1">
                  <HoldingList rows={p.largest_positions} empty="No priced holdings yet." />
                </Panel>
                <Panel title="Recent additions" bodyClassName="px-4 py-1"
                  actions={<Link href="/portfolio" className="text-xs text-ink-3 hover:text-ink">Portfolio →</Link>}>
                  <HoldingList rows={p.recent_additions} empty="Nothing added yet."
                    right={(h) => <div className="text-xs text-ink-3">{day(h.acquisition_date ?? h.added_at)}</div>} />
                </Panel>
              </div>
            </>
          ) : (
            <Panel>
              <EmptyState icon={Wallet} title="Start tracking your collection" action={<AddFirstCta />}>
                Add the cards and sealed product you own. Values, profit/loss, binder progress and grading economics
                are calculated from live market prices — nothing is estimated until real prices exist.
              </EmptyState>
            </Panel>
          )}
        </div>
      )}
    </>
  );
}

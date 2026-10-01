"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { HistoryPending } from "@/components/ui";
import type { Group, PortfolioHistory, PortfolioOverview } from "@/lib/dashboard";
import { CHART, tooltipStyle } from "@/lib/chart";
import { day, nok, nokCompact, pct } from "@/lib/format";

const axisProps = { tick: CHART.tick, stroke: CHART.grid, tickLine: false } as const;
const yFmt = (v: number) => nokCompact(v).replace(" NOK", "");
const tipFmt = (v: unknown) => nok(typeof v === "number" ? v : Number(v));
const legendStyle = { fontSize: 12, color: "#a3a9b8", paddingTop: 4 };
const tickDay = (d: string) =>
  new Date(`${d}T12:00:00Z`).toLocaleDateString("nb-NO", { day: "numeric", month: "short" });

/** Market value vs cost basis over time (daily portfolio snapshots). One NOK axis. */
export function ValueHistoryChart({ history, height = 240 }: { history: PortfolioHistory; height?: number }) {
  if (!history.ready) return <HistoryPending what="Portfolio value history" detail="One snapshot is taken per day; the chart starts once two days exist." />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={history.points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={CHART.grid} vertical={false} />
        <XAxis dataKey="day" {...axisProps} tickFormatter={tickDay} minTickGap={24} />
        <YAxis {...axisProps} width={52} tickFormatter={yFmt} />
        <Tooltip {...tooltipStyle} formatter={tipFmt} labelFormatter={(d) => day(String(d))} />
        <Legend wrapperStyle={legendStyle} iconType="plainline" />
        <Line type="monotone" dataKey="value_nok" name="Market value" stroke={CHART.series.value} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
        <Line type="monotone" dataKey="cost_nok" name="Cost basis" stroke={CHART.series.cost} strokeWidth={2} strokeDasharray="5 4" dot={false} activeDot={{ r: 4 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Unrealised profit/loss over time, with a zero baseline. */
export function PnlHistoryChart({ history, height = 200 }: { history: PortfolioHistory; height?: number }) {
  if (!history.ready) return <HistoryPending what="Profit/loss history" detail="One snapshot is taken per day; the chart starts once two days exist." />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={history.points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={CHART.grid} vertical={false} />
        <XAxis dataKey="day" {...axisProps} tickFormatter={tickDay} minTickGap={24} />
        <YAxis {...axisProps} width={52} tickFormatter={yFmt} />
        <ReferenceLine y={0} stroke={CHART.axis} strokeDasharray="3 3" />
        <Tooltip {...tooltipStyle} formatter={tipFmt} labelFormatter={(d) => day(String(d))} />
        <Line type="monotone" dataKey="gain_nok" name="Unrealised P/L" stroke={CHART.series.value} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

const KIND_LABELS: Record<string, string> = { raw: "Raw cards", graded: "Graded", sealed: "Sealed" };

/** Acquisition cost vs current market value per holding kind (current, not historical). */
export function CostValueBars({ byKind, height = 220 }: { byKind: PortfolioOverview["by_kind"]; height?: number }) {
  const data = (Object.entries(byKind) as [string, Group][])
    .filter(([, g]) => g.count > 0)
    .map(([k, g]) => ({ kind: KIND_LABELS[k] ?? k, cost: g.cost_nok, value: g.value_nok }));
  if (!data.length) return <HistoryPending what="Cost vs value" detail="Add holdings to compare what you paid with what they are worth." />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barGap={2} barCategoryGap="28%">
        <CartesianGrid stroke={CHART.grid} vertical={false} />
        <XAxis dataKey="kind" {...axisProps} />
        <YAxis {...axisProps} width={52} tickFormatter={yFmt} />
        <Tooltip {...tooltipStyle} formatter={tipFmt} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
        <Legend wrapperStyle={legendStyle} />
        <Bar dataKey="cost" name="Cost" fill={CHART.series.cost} radius={[4, 4, 0, 0]} maxBarSize={36} />
        <Bar dataKey="value" name="Market value" fill={CHART.series.value} radius={[4, 4, 0, 0]} maxBarSize={36} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/**
 * Allocation by holding kind as labelled horizontal bars (one colour, direct labels):
 * clearer than a donut for three close parts and needs no categorical palette.
 */
export function AllocationBars({ allocation }: { allocation: PortfolioOverview["allocation"] }) {
  const total = allocation.reduce((s, a) => s + a.value_nok, 0);
  if (!allocation.length || total <= 0) {
    return <HistoryPending what="Allocation" detail="Appears once your holdings have market prices." />;
  }
  return (
    <div className="space-y-3">
      {allocation.map((a) => {
        const share = a.value_nok / total;
        return (
          <div key={a.kind}>
            <div className="mb-1 flex items-baseline justify-between gap-2 text-sm">
              <span className="text-ink-2">
                {KIND_LABELS[a.kind] ?? a.kind} <span className="text-xs text-ink-3">· {a.count} item{a.count === 1 ? "" : "s"}</span>
              </span>
              <span className="num text-ink">
                {nok(a.value_nok)} <span className="text-xs text-ink-3">{pct(share, 0)}</span>
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-surface-3" title={`${pct(share, 1)} of market value`}>
              <div className="h-full rounded-full bg-gold" style={{ width: `${Math.max(share * 100, 1)}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

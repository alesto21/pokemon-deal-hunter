"use client";

import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHART, tooltipStyle } from "@/lib/chart";
import { nok } from "@/lib/format";
import { SERIES, SERIES_LABEL } from "./palette";

export interface PricePoint {
  label: string; // x-axis label (day or scan time)
  low: number | null;
  c5: number | null;
  fair?: number | null;
}

/**
 * One y-axis (NOK) line chart: market low, cheapest-5 median and (when known) fair value.
 * Gaps stay gaps — nothing is interpolated across days without data.
 * `fairNow` draws today's fair value as a dashed reference (used for per-scan charts,
 * where fair value is not stored per scan).
 */
export default function PriceHistoryChart({ data, fairNow, height = 300 }: { data: PricePoint[]; fairNow?: number | null; height?: number }) {
  const hasFair = data.some((d) => d.fair !== null && d.fair !== undefined);
  // Explicit domain so a "fair value now" reference line is never clipped out of view.
  const vals = data.flatMap((d) => [d.low, d.c5, d.fair]).filter((v): v is number => typeof v === "number");
  if (!hasFair && fairNow) vals.push(fairNow);
  const lo = vals.length ? Math.min(...vals) : 0;
  const hi = vals.length ? Math.max(...vals) : 1;
  const pad = Math.max((hi - lo) * 0.08, hi * 0.02);
  const domain: [number, number] = [Math.max(0, Math.floor(lo - pad)), Math.ceil(hi + pad)];
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
          <CartesianGrid stroke={CHART.grid} strokeDasharray="2 4" vertical={false} />
          <XAxis dataKey="label" tick={CHART.tick} tickLine={false} axisLine={{ stroke: CHART.grid }} minTickGap={24} />
          <YAxis
            tick={CHART.tick}
            tickLine={false}
            axisLine={false}
            width={56}
            domain={domain}
            tickFormatter={(v: number) => (v >= 10000 ? `${Math.round(v / 1000)}k` : String(Math.round(v)))}
          />
          <Tooltip
            {...tooltipStyle}
            cursor={{ stroke: CHART.axis, strokeDasharray: "3 3" }}
            formatter={(v) => (typeof v === "number" ? nok(v) : "—")}
          />
          <Legend iconType="plainline" wrapperStyle={{ fontSize: 12, color: "#a3a9b8", paddingTop: 4 }} />
          <Line type="monotone" dataKey="low" name={SERIES_LABEL.low} stroke={SERIES.low} strokeWidth={2} dot={data.length < 20 ? { r: 3, strokeWidth: 2, stroke: "#0e1015" } : false} activeDot={{ r: 4 }} isAnimationActive={false} />
          <Line type="monotone" dataKey="c5" name={SERIES_LABEL.c5} stroke={SERIES.c5} strokeWidth={2} dot={data.length < 20 ? { r: 3, strokeWidth: 2, stroke: "#0e1015" } : false} activeDot={{ r: 4 }} isAnimationActive={false} />
          {hasFair && (
            <Line type="monotone" dataKey="fair" name={SERIES_LABEL.fair} stroke={SERIES.fair} strokeWidth={2} strokeDasharray="6 4" dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
          )}
          {!hasFair && fairNow ? (
            <ReferenceLine y={fairNow} stroke={SERIES.fair} strokeDasharray="6 4" strokeWidth={1.5} label={{ value: `Fair value now ${nok(fairNow)}`, fill: "#a3a9b8", fontSize: 11, position: "insideTopRight" }} />
          ) : null}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

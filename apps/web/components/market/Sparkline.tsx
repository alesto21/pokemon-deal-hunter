"use client";

import { SERIES } from "./palette";

/**
 * Tiny inline trend of daily cheapest-5 medians. Needs ≥ 2 real points; otherwise it says
 * history is being collected (nothing is interpolated or back-filled).
 */
export default function Sparkline({
  points,
  width = 120,
  height = 32,
  label = "cheapest-5",
}: {
  points: (number | null)[];
  width?: number;
  height?: number;
  label?: string;
}) {
  const vals = points.filter((v): v is number => v !== null && v !== undefined);
  if (vals.length < 2) {
    return (
      <div className="text-[11px] leading-tight text-ink-3" style={{ width }}>
        History collecting
        <br />
        {vals.length} day{vals.length === 1 ? "" : "s"} so far
      </div>
    );
  }
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const step = width / (vals.length - 1);
  const y = (v: number) => height - 3 - ((v - min) / span) * (height - 6);
  const d = vals.map((v, i) => `${i ? "L" : "M"}${(i * step).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const last = vals[vals.length - 1];
  const first = vals[0];
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${label} trend over ${vals.length} days`}>
      <title>{`${label}: ${Math.round(first)} → ${Math.round(last)} NOK over ${vals.length} days`}</title>
      <path d={d} fill="none" stroke={SERIES.c5} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={(vals.length - 1) * step} cy={y(last)} r={3} fill={SERIES.c5} stroke="#0e1015" strokeWidth={2} />
    </svg>
  );
}

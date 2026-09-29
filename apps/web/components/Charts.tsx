"use client";

import {
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
import type { PriceHistory } from "@/lib/types";

const COLORS = { median: "#2563eb", trimmed: "#7c3aed", low: "#059669", count: "#9ca3af", cost: "#9ca3af", value: "#2563eb" };

export function PriceChart({ data }: { data: PriceHistory }) {
  const rows = data.daily.map((d) => ({ ...d }));
  return (
    <ResponsiveContainer width="100%" height={340}>
      <LineChart data={rows} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#8882" />
        <XAxis dataKey="day" tick={{ fontSize: 11 }} />
        <YAxis yAxisId="nok" tick={{ fontSize: 11 }} width={60} />
        <YAxis yAxisId="count" orientation="right" tick={{ fontSize: 11 }} width={40} />
        <Tooltip />
        <Legend />
        <Line yAxisId="nok" type="monotone" dataKey="median" name="Median" stroke={COLORS.median} dot={false} connectNulls />
        <Line yAxisId="nok" type="monotone" dataKey="trimmed_median" name="Trimmed median" stroke={COLORS.trimmed} dot={false} connectNulls />
        <Line yAxisId="nok" type="monotone" dataKey="low" name="Low" stroke={COLORS.low} dot={false} connectNulls />
        <Line yAxisId="count" type="stepAfter" dataKey="listing_count" name="Listings" stroke={COLORS.count} strokeDasharray="4 3" dot={false} connectNulls />
        {data.portfolio_entries.map((e, i) => (
          <ReferenceLine
            key={i}
            yAxisId="nok"
            y={e.price_nok}
            stroke="#f59e0b"
            strokeDasharray="6 3"
            label={{ value: `bought ${Math.round(e.price_nok)}`, fontSize: 10, fill: "#f59e0b", position: "insideTopLeft" }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function PortfolioChart({ history }: { history: { day: string; cost: number; value: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={history} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#8882" />
        <XAxis dataKey="day" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} width={70} />
        <Tooltip />
        <Legend />
        <Line type="monotone" dataKey="value" name="Value (NOK)" stroke={COLORS.value} dot={false} />
        <Line type="monotone" dataKey="cost" name="Cost (NOK)" stroke={COLORS.cost} strokeDasharray="4 3" dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

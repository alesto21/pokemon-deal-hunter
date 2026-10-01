import { CHART } from "@/lib/chart";

/** Price-history series (colours live in lib/chart.ts — the single validated palette). */
export const SERIES = {
  low: CHART.series.low,
  c5: CHART.series.c5,
  fair: CHART.series.fair,
} as const;

export const SERIES_LABEL = {
  low: "Market low",
  c5: "Cheapest-5 median",
  fair: "Fair value",
} as const;

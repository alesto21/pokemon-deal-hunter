/**
 * Shared, restrained chart styling (dark theme). Single source for every chart.
 * Series colours are validated with the dataviz validator on the dark surface (#0e1015):
 * lightness band, chroma, CVD ΔE 19.6, normal ΔE 20.9, contrast ≥ 3:1 — all pass.
 * Fair value is additionally drawn dashed (secondary encoding, not colour alone).
 */
export const CHART = {
  grid: "#232834",
  axis: "#6b7283",
  tooltipBg: "#151821",
  tooltipBorder: "#2f3543",
  series: {
    value: "#c98500", // amber — portfolio value
    cost: "#6b7283", // grey — cost basis (context, not data emphasis)
    low: "#199e70", // aqua — market low
    c5: "#3987e5", // blue — cheapest-5 median (buyable)
    fair: "#c98500", // amber — fair value (drawn dashed)
    gain: "#34d399",
    loss: "#f87171",
  },
  allocation: ["#e5b94e", "#60a5fa", "#a78bfa", "#34d399"],
  tick: { fontSize: 11, fill: "#6b7283" },
} as const;

export const tooltipStyle = {
  contentStyle: { background: CHART.tooltipBg, border: `1px solid ${CHART.tooltipBorder}`, borderRadius: 8, fontSize: 12 },
  labelStyle: { color: "#a3a9b8" },
  itemStyle: { color: "#e8eaf0" },
} as const;

export function nok(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const s = new Intl.NumberFormat("nb-NO", { maximumFractionDigits: digits, minimumFractionDigits: digits })
    .format(v)
    .replace(/\u00a0|\u202f/g, " ")
    .replace("−", "-");
  return `${s} NOK`;
}

export function pct(v: number | null | undefined, digits = 1, signed = false): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const s = (v * 100).toFixed(digits);
  return `${signed && v > 0 ? "+" : ""}${s}%`;
}

export function num(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

export function dt(v: string | null | undefined): string {
  if (!v) return "—";
  // API returns naive UTC timestamps.
  const d = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(v) ? v : `${v}Z`);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleString("nb-NO", { dateStyle: "short", timeStyle: "short" });
}

export function gainClass(v: number | null | undefined): string {
  if (v === null || v === undefined || v === 0) return "";
  return v > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400";
}

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

/** Compact NOK for tight spots: 1 234 NOK, 12,3k NOK, 1,2M NOK. */
export function nokCompact(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const a = Math.abs(v);
  if (a < 10_000) return nok(v);
  const n = new Intl.NumberFormat("nb-NO", { notation: "compact", maximumFractionDigits: 1 }).format(v);
  return `${n.replace(/\u00a0|\u202f/g, " ").replace("−", "-")} NOK`;
}

function parseUtc(v: string): Date {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(v) ? v : `${v}Z`);
}

/** Date only (API dates like "2026-09-30" or UTC timestamps). */
export function day(v: string | null | undefined): string {
  if (!v) return "—";
  const d = /^\d{4}-\d{2}-\d{2}$/.test(v) ? new Date(`${v}T12:00:00Z`) : parseUtc(v);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleDateString("nb-NO", { day: "2-digit", month: "short", year: "numeric" });
}

/** "5 min ago" / "in 12 min" relative to now, for UTC timestamps. */
export function rel(v: string | null | undefined): string {
  if (!v) return "—";
  const d = parseUtc(v);
  if (Number.isNaN(d.getTime())) return v;
  const s = Math.round((d.getTime() - Date.now()) / 1000);
  const a = Math.abs(s);
  const f = (n: number, u: string) => (s < 0 ? `${n} ${u} ago` : `in ${n} ${u}`);
  if (a < 60) return s < 0 ? "just now" : "in <1 min";
  if (a < 3600) return f(Math.round(a / 60), "min");
  if (a < 86400) return f(Math.round(a / 3600), "h");
  return f(Math.round(a / 86400), "d");
}

export function bytes(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const u = ["B", "KB", "MB", "GB"];
  let n = v;
  let i = 0;
  while (n >= 1024 && i < u.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n.toFixed(i ? 1 : 0)} ${u[i]}`;
}

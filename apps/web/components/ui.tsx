import type { ReactNode } from "react";
import type { Recommendation } from "@/lib/types";

export const btn =
  "inline-flex items-center gap-1 rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:bg-zinc-800";
export const btnPrimary =
  "inline-flex items-center gap-1 rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300";
export const btnDanger =
  "inline-flex items-center gap-1 rounded-md border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950";
export const input =
  "w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900";
export const th = "px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500";
export const td = "px-3 py-2 align-top text-sm";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-zinc-500">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Panel({ title, children, actions, className = "" }: { title?: string; children: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950 ${className}`}>
      {(title || actions) && (
        <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-2.5 dark:border-zinc-800">
          {title && <h2 className="text-sm font-semibold">{title}</h2>}
          {actions}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function StatTile({ label, value, hint, className = "" }: { label: string; value: ReactNode; hint?: ReactNode; className?: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="text-xs uppercase tracking-wide text-zinc-500">{label}</div>
      <div className={`mt-1 text-xl font-semibold tabular-nums ${className}`}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-zinc-500">{hint}</div>}
    </div>
  );
}

const REC_STYLE: Record<Recommendation, string> = {
  STEAL: "bg-red-600 text-white",
  STRONG_BUY: "bg-orange-500 text-white",
  GOOD: "bg-emerald-600 text-white",
  WATCH: "bg-zinc-300 text-zinc-800 dark:bg-zinc-700 dark:text-zinc-100",
  IGNORE: "bg-zinc-100 text-zinc-400 dark:bg-zinc-900 dark:text-zinc-500",
};
const REC_LABEL: Record<Recommendation, string> = {
  STEAL: "🚨 STEAL",
  STRONG_BUY: "🔥 STRONG BUY",
  GOOD: "👀 GOOD",
  WATCH: "WATCH",
  IGNORE: "IGNORE",
};

export function RecBadge({ rec }: { rec: Recommendation | string | null | undefined }) {
  if (!rec) return <span className="text-zinc-400">—</span>;
  const r = rec as Recommendation;
  return (
    <span className={`inline-block whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-semibold ${REC_STYLE[r] ?? "bg-zinc-200"}`}>
      {REC_LABEL[r] ?? rec}
    </span>
  );
}

export function HealthDot({ healthy }: { healthy: boolean | null | undefined }) {
  const cls = healthy === null || healthy === undefined ? "bg-zinc-400" : healthy ? "bg-emerald-500" : "bg-red-500";
  const label = healthy === null || healthy === undefined ? "disabled" : healthy ? "healthy" : "unhealthy";
  return <span title={label} className={`inline-block h-2.5 w-2.5 rounded-full ${cls}`} />;
}

export function ErrorBox({ error }: { error: string | null | undefined }) {
  if (!error) return null;
  return (
    <div className="mb-4 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
      {error}
    </div>
  );
}

export function Loading({ show = true }: { show?: boolean }) {
  if (!show) return null;
  return <div className="py-6 text-center text-sm text-zinc-500">Loading…</div>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="py-6 text-center text-sm text-zinc-500">{children}</div>;
}

"use client";

import { ChevronDown, ImageOff, type LucideIcon, TriangleAlert } from "lucide-react";
import { type ReactNode, useState } from "react";
import { gainClass, nok, pct } from "@/lib/format";
import type { Recommendation } from "@/lib/types";

/* ============================================================== class tokens */
export const btn =
  "inline-flex items-center justify-center gap-1.5 rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-sm font-medium text-ink hover:bg-surface-3 disabled:opacity-40";
export const btnPrimary =
  "inline-flex items-center justify-center gap-1.5 rounded-lg bg-gold px-3 py-1.5 text-sm font-semibold text-canvas hover:brightness-110 disabled:opacity-40";
export const btnGhost =
  "inline-flex items-center justify-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-ink-2 hover:bg-surface-2 hover:text-ink disabled:opacity-40";
export const btnDanger =
  "inline-flex items-center justify-center gap-1 rounded-lg border border-loss/40 px-2 py-1 text-xs text-loss hover:bg-loss/10";
export const input =
  "w-full rounded-lg border border-line bg-surface-2 px-2.5 py-1.5 text-sm text-ink placeholder:text-ink-3 focus:border-line-strong focus:outline-none";
export const th = "px-3 py-2 text-left text-[11px] font-medium uppercase tracking-wider text-ink-3";
export const td = "px-3 py-2.5 align-middle text-sm";

/* ============================================================== layout */
export function PageHeader({
  title,
  subtitle,
  actions,
  icon: Icon,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  icon?: LucideIcon;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight text-ink sm:text-2xl">
          {Icon && <Icon size={22} className="text-gold" />}
          {title}
        </h1>
        {subtitle && <p className="mt-1 text-sm text-ink-3">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Panel({
  title,
  subtitle,
  children,
  actions,
  className = "",
  bodyClassName = "p-4",
  icon: Icon,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
  actions?: ReactNode;
  className?: string;
  bodyClassName?: string;
  icon?: LucideIcon;
}) {
  return (
    <section className={`rounded-xl border border-line bg-surface ${className}`}>
      {(title || actions) && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
          <div className="min-w-0">
            {title && (
              <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
                {Icon && <Icon size={15} className="text-ink-3" />}
                {title}
              </h2>
            )}
            {subtitle && <p className="mt-0.5 text-xs text-ink-3">{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}

/** Big number tile for KPI rows. `tone` colours the value (gain/loss/gold). */
export function KpiCard({
  label,
  value,
  hint,
  icon: Icon,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: LucideIcon;
  tone?: "gain" | "loss" | "gold" | null;
}) {
  const toneCls = tone === "gain" ? "text-gain" : tone === "loss" ? "text-loss" : tone === "gold" ? "text-gold" : "text-ink";
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="text-[11px] font-medium uppercase tracking-wider text-ink-3">{label}</div>
        {Icon && <Icon size={15} className="text-ink-3" />}
      </div>
      <div className={`num mt-1.5 truncate text-xl font-semibold sm:text-2xl ${toneCls}`}>{value}</div>
      {hint && <div className="mt-1 truncate text-xs text-ink-3">{hint}</div>}
    </div>
  );
}

/** Backwards-compatible small stat tile. */
export function StatTile({ label, value, hint, className = "" }: { label: string; value: ReactNode; hint?: ReactNode; className?: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <div className="text-[11px] font-medium uppercase tracking-wider text-ink-3">{label}</div>
      <div className={`num mt-1 text-lg font-semibold ${className}`}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-ink-3">{hint}</div>}
    </div>
  );
}

/** Label / value row for detail panels. */
export function Field({ label, value, className = "" }: { label: ReactNode; value: ReactNode; className?: string }) {
  return (
    <div className={`flex items-baseline justify-between gap-3 py-1 text-sm ${className}`}>
      <span className="text-ink-3">{label}</span>
      <span className="num text-right text-ink">{value}</span>
    </div>
  );
}

/* ============================================================== badges */
const LEVEL_STYLE: Record<Recommendation, string> = {
  STEAL: "bg-rose-500/15 text-rose-300 ring-rose-400/40",
  STRONG_BUY: "bg-orange-500/15 text-orange-300 ring-orange-400/40",
  GOOD: "bg-emerald-500/15 text-emerald-300 ring-emerald-400/40",
  WATCH: "bg-sky-500/10 text-sky-300 ring-sky-400/25",
  IGNORE: "bg-surface-3 text-ink-3 ring-line",
};
const LEVEL_LABEL: Record<Recommendation, string> = {
  STEAL: "Steal",
  STRONG_BUY: "Strong buy",
  GOOD: "Good",
  WATCH: "Watch",
  IGNORE: "Ignore",
};

/** Recommendation badge. Always pass the EFFECTIVE level (after caps), never the raw band. */
export function LevelBadge({ level, size = "sm" }: { level: Recommendation | string | null | undefined; size?: "sm" | "md" }) {
  if (!level) return <span className="text-ink-3">—</span>;
  const l = level as Recommendation;
  const sz = size === "md" ? "px-2.5 py-1 text-xs" : "px-2 py-0.5 text-[11px]";
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-full font-semibold uppercase tracking-wide ring-1 ring-inset ${sz} ${LEVEL_STYLE[l] ?? LEVEL_STYLE.IGNORE}`}>
      {LEVEL_LABEL[l] ?? level}
    </span>
  );
}

/** @deprecated use LevelBadge; kept for existing pages. */
export const RecBadge = ({ rec }: { rec: Recommendation | string | null | undefined }) => <LevelBadge level={rec} />;

type Tone = "neutral" | "gain" | "loss" | "warn" | "info" | "gold";
const TONE: Record<Tone, string> = {
  neutral: "bg-surface-3 text-ink-2 ring-line",
  gain: "bg-emerald-500/10 text-emerald-300 ring-emerald-400/30",
  loss: "bg-rose-500/10 text-rose-300 ring-rose-400/30",
  warn: "bg-amber-500/10 text-amber-300 ring-amber-400/30",
  info: "bg-sky-500/10 text-sky-300 ring-sky-400/30",
  gold: "bg-gold-soft text-gold ring-gold/30",
};

export function Badge({ children, tone = "neutral", title }: { children: ReactNode; tone?: Tone; title?: string }) {
  return (
    <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset ${TONE[tone]}`}>
      {children}
    </span>
  );
}

export function HealthDot({ healthy }: { healthy: boolean | null | undefined }) {
  const cls = healthy === null || healthy === undefined ? "bg-ink-3" : healthy ? "bg-gain" : "bg-loss";
  const label = healthy === null || healthy === undefined ? "disabled" : healthy ? "healthy" : "unhealthy";
  return <span title={label} className={`inline-block h-2 w-2 shrink-0 rounded-full ${cls}`} />;
}

/* ============================================================== numbers */
/** Signed NOK with gain/loss colour. */
export function Delta({ nokValue, pctValue, className = "" }: { nokValue?: number | null; pctValue?: number | null; className?: string }) {
  const v = nokValue ?? pctValue;
  return (
    <span className={`num ${gainClass(v)} ${className}`}>
      {nokValue !== undefined && nokValue !== null && `${nokValue > 0 ? "+" : ""}${nok(nokValue)}`}
      {nokValue !== undefined && nokValue !== null && pctValue !== undefined && pctValue !== null && " · "}
      {pctValue !== undefined && pctValue !== null && pct(pctValue, 1, true)}
      {(nokValue === undefined || nokValue === null) && (pctValue === undefined || pctValue === null) && "—"}
    </span>
  );
}

export function ProgressBar({ value, tone = "gold", className = "" }: { value: number | null | undefined; tone?: "gold" | "gain" | "info"; className?: string }) {
  const w = Math.max(0, Math.min(1, value ?? 0)) * 100;
  const bar = tone === "gain" ? "bg-gain" : tone === "info" ? "bg-info" : "bg-gold";
  return (
    <div className={`h-2 w-full overflow-hidden rounded-full bg-surface-3 ${className}`}>
      <div className={`h-full rounded-full ${bar}`} style={{ width: `${w}%` }} />
    </div>
  );
}

/* ============================================================== media */
/** Card/product image with a quiet fallback. Images are CardTrader previews already in our DB. */
export function CardThumb({ src, alt, size = "md", className = "" }: { src?: string | null; alt: string; size?: "sm" | "md" | "lg"; className?: string }) {
  const [failed, setFailed] = useState(false);
  const dims = size === "sm" ? "h-12 w-9" : size === "lg" ? "h-44 w-32" : "h-16 w-12";
  if (!src || failed) {
    return (
      <div className={`${dims} grid shrink-0 place-items-center rounded-md border border-line bg-surface-2 text-ink-3 ${className}`}>
        <ImageOff size={14} />
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element -- external CardTrader preview, no optimisation needed
    <img
      src={src}
      alt={alt}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      className={`${dims} shrink-0 rounded-md border border-line bg-surface-2 object-cover ${className}`}
    />
  );
}

/* ============================================================== states */
export function ErrorBox({ error }: { error: string | null | undefined }) {
  if (!error) return null;
  return (
    <div className="mb-4 flex items-start gap-2 rounded-xl border border-loss/30 bg-loss/10 px-3 py-2.5 text-sm text-rose-200">
      <TriangleAlert size={16} className="mt-0.5 shrink-0" />
      {error}
    </div>
  );
}

export function Loading({ show = true, label = "Loading…" }: { show?: boolean; label?: string }) {
  if (!show) return null;
  return (
    <div className="space-y-3 py-2" aria-busy="true" aria-label={label}>
      <div className="h-24 animate-pulse rounded-xl bg-surface" />
      <div className="h-48 animate-pulse rounded-xl bg-surface" />
    </div>
  );
}

export function Skeleton({ className = "h-5 w-full" }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-surface-3 ${className}`} />;
}

/** Friendly empty state. Use it instead of zeros whenever data does not exist yet. */
export function EmptyState({ icon: Icon, title, children, action }: { icon?: LucideIcon; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-10 text-center">
      {Icon && (
        <div className="mb-3 grid h-11 w-11 place-items-center rounded-full bg-surface-3 text-ink-3">
          <Icon size={20} />
        </div>
      )}
      <div className="text-sm font-medium text-ink">{title}</div>
      {children && <div className="mt-1 max-w-md text-sm text-ink-3">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/** @deprecated simple empty line; prefer EmptyState. */
export function Empty({ children }: { children: ReactNode }) {
  return <div className="py-6 text-center text-sm text-ink-3">{children}</div>;
}

/** Placeholder for charts that need history the system has not collected yet. */
export function HistoryPending({ what = "History", detail }: { what?: string; detail?: ReactNode }) {
  return (
    <div className="grid h-full min-h-40 place-items-center rounded-lg border border-dashed border-line px-4 py-8 text-center">
      <div>
        <div className="text-sm font-medium text-ink-2">{what} is being collected</div>
        <div className="mt-1 text-xs text-ink-3">{detail ?? "Charts appear once at least two days of real data exist. Nothing is back-filled."}</div>
      </div>
    </div>
  );
}

/* ============================================================== interactive */
export function Disclosure({ title, children, defaultOpen = false }: { title: ReactNode; children: ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-lg border border-line">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm text-ink-2 hover:text-ink">
        {title}
        <ChevronDown size={16} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <div className="border-t border-line px-3 py-3">{children}</div>}
    </div>
  );
}

export function Segmented<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode }[] }) {
  return (
    <div className="inline-flex rounded-lg border border-line bg-surface-2 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`rounded-md px-2.5 py-1 text-xs font-medium ${value === o.value ? "bg-surface-3 text-ink" : "text-ink-3 hover:text-ink-2"}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ============================================================== responsive table */
export interface Column<T> {
  key: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  align?: "left" | "right";
  className?: string;
  /** Hide below this breakpoint in table mode. */
  hideBelow?: "md" | "lg" | "xl";
}

/**
 * Table on md+ screens; stacked cards on phones (`mobileCard` renders each row).
 * Keeps phones free of horizontally scrolling giant tables.
 */
export function DataTable<T>({
  rows,
  columns,
  rowKey,
  mobileCard,
  onRowClick,
  empty,
}: {
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string | number;
  mobileCard: (row: T) => ReactNode;
  onRowClick?: (row: T) => void;
  empty?: ReactNode;
}) {
  if (!rows.length) return <>{empty ?? <Empty>Nothing to show.</Empty>}</>;
  const hide = (c: Column<T>) =>
    c.hideBelow === "md" ? "hidden md:table-cell" : c.hideBelow === "lg" ? "hidden lg:table-cell" : c.hideBelow === "xl" ? "hidden xl:table-cell" : "";
  return (
    <>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full">
          <thead className="border-b border-line">
            <tr>
              {columns.map((c) => (
                <th key={c.key} className={`${th} ${c.align === "right" ? "text-right" : ""} ${hide(c)} ${c.className ?? ""}`}>
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line/70">
            {rows.map((r) => (
              <tr key={rowKey(r)} onClick={onRowClick ? () => onRowClick(r) : undefined} className={onRowClick ? "cursor-pointer hover:bg-surface-2" : ""}>
                {columns.map((c) => (
                  <td key={c.key} className={`${td} ${c.align === "right" ? "num text-right" : ""} ${hide(c)} ${c.className ?? ""}`}>
                    {c.cell(r)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="space-y-2 md:hidden">
        {rows.map((r) => (
          <div
            key={rowKey(r)}
            onClick={onRowClick ? () => onRowClick(r) : undefined}
            className={`rounded-xl border border-line bg-surface-2 p-3 ${onRowClick ? "cursor-pointer active:bg-surface-3" : ""}`}
          >
            {mobileCard(r)}
          </div>
        ))}
      </div>
    </>
  );
}

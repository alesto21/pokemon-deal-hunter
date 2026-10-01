"use client";

import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export type Status = "ok" | "warn" | "bad" | "off";

const STATUS: Record<Status, { dot: string; label: string; ring: string }> = {
  ok: { dot: "bg-gain", label: "text-gain", ring: "border-line" },
  warn: { dot: "bg-warn", label: "text-warn", ring: "border-amber-400/30" },
  bad: { dot: "bg-loss", label: "text-loss", ring: "border-loss/40" },
  off: { dot: "bg-ink-3", label: "text-ink-3", ring: "border-line" },
};

/** Compact status card used on the System and Sources pages. */
export default function StatusCard({
  title,
  icon: Icon,
  status,
  statusLabel,
  children,
  footer,
}: {
  title: string;
  icon: LucideIcon;
  status: Status;
  statusLabel: string;
  children?: ReactNode;
  footer?: ReactNode;
}) {
  const s = STATUS[status];
  return (
    <section className={`flex flex-col rounded-xl border bg-surface ${s.ring}`}>
      <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-3">
        <h2 className="flex min-w-0 items-center gap-2 text-sm font-semibold text-ink">
          <Icon size={15} className="shrink-0 text-ink-3" />
          <span className="truncate">{title}</span>
        </h2>
        <span className={`flex shrink-0 items-center gap-1.5 text-xs font-medium ${s.label}`}>
          <span className={`h-2 w-2 rounded-full ${s.dot}`} />
          {statusLabel}
        </span>
      </div>
      <div className="flex-1 px-4 py-2.5">{children}</div>
      {footer && <div className="border-t border-line px-4 py-2.5">{footer}</div>}
    </section>
  );
}

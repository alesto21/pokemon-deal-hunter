"use client";

import { Activity, ChevronRight } from "lucide-react";
import Link from "next/link";
import type { SystemMini } from "@/lib/dashboard";
import { rel } from "@/lib/format";

const NAMES: Record<string, string> = { cardtrader: "CardTrader scanner", stores: "Web shops" };

/** One-line scanner status per scheduled source; links to /system for detail. */
export function SystemStrip({ system }: { system: SystemMini[] }) {
  if (!system.length) {
    return (
      <Link href="/system" className="flex items-center justify-between rounded-xl border border-line bg-surface px-4 py-2.5 text-sm text-ink-3 hover:bg-surface-2">
        No scheduled sources enabled <ChevronRight size={15} />
      </Link>
    );
  }
  return (
    <Link href="/system" className="group block rounded-xl border border-line bg-surface hover:bg-surface-2">
      {system.map((s) => {
        const w = s.worker;
        const state = w.next_scan_overdue
          ? { dot: "bg-loss", text: "Worker overdue", tone: "text-rose-300" }
          : !w.worker_scheduled
            ? { dot: "bg-loss", text: "Not scheduled", tone: "text-rose-300" }
            : s.lock.locked && !s.lock.stale
              ? { dot: "bg-info", text: "Scanning now", tone: "text-sky-300" }
              : s.healthy === false
                ? { dot: "bg-warn", text: "Recent errors", tone: "text-amber-300" }
                : { dot: "bg-gain", text: "Healthy", tone: "text-emerald-300" };
        return (
          <div key={s.source} className="flex flex-wrap items-center gap-x-5 gap-y-1 px-4 py-2.5 text-sm">
            <span className="flex items-center gap-2 font-medium text-ink">
              <Activity size={15} className="text-ink-3" />
              {NAMES[s.source] ?? s.source}
              <span className="text-xs font-normal text-ink-3">({s.mode})</span>
            </span>
            <span className={`flex items-center gap-1.5 ${state.tone}`}>
              <span className={`h-2 w-2 rounded-full ${state.dot}`} />
              {state.text}
            </span>
            <span className="text-ink-3">
              Last scan <span className="text-ink-2">{rel(w.last_successful_scan)}</span>
            </span>
            <span className="text-ink-3">
              Next <span className={w.next_scan_overdue ? "text-rose-300" : "text-ink-2"}>{w.next_scheduled_scan ? rel(w.next_scheduled_scan) : "—"}</span>
            </span>
            <ChevronRight size={15} className="ml-auto text-ink-3 group-hover:text-ink-2" />
          </div>
        );
      })}
    </Link>
  );
}

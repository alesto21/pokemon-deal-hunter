"use client";

import { Field } from "@/components/ui";
import type { ScanLock, WorkerSchedule } from "@/lib/dashboard";
import { dt, rel } from "@/lib/format";

function seconds(s: number | null | undefined): string {
  if (s === null || s === undefined) return "—";
  if (s < 10) return `${s.toFixed(1)} s`;
  if (s < 90) return `${Math.round(s)} s`;
  if (s < 5400) return `${Math.round(s / 60)} min`;
  return `${(s / 3600).toFixed(1)} h`;
}

/** Next-scan line: OVERDUE is shown prominently; the stored timestamp is kept for diagnosis. */
export function NextScan({ worker, enabled = true }: { worker: WorkerSchedule; enabled?: boolean }) {
  if (worker.next_scan_overdue) {
    return (
      <span className="font-semibold text-loss" title={`was due ${dt(worker.next_scheduled_scan)}`}>
        OVERDUE {seconds(worker.next_scan_overdue_seconds)}
      </span>
    );
  }
  if (worker.next_scheduled_scan) {
    return (
      <span title={dt(worker.next_scheduled_scan)}>
        {rel(worker.next_scheduled_scan)} <span className="text-ink-3">· {dt(worker.next_scheduled_scan)}</span>
      </span>
    );
  }
  return <span className="text-ink-3">{enabled ? "not scheduled (worker stopped)" : "—"}</span>;
}

export function lockLabel(lock: ScanLock): { text: string; tone: "ok" | "warn" | "bad" } {
  if (!lock.locked) return { text: "free", tone: "ok" };
  if (lock.stale) return { text: `stale — heartbeat ${seconds(lock.heartbeat_age_seconds)} ago`, tone: "bad" };
  return { text: `held ${seconds(lock.age_seconds)}`, tone: "warn" };
}

/** Scan-lock rows. Owner is a raw process id, so it stays out of the default view unless held. */
export function LockRows({ lock, showOwner = true }: { lock: ScanLock; showOwner?: boolean }) {
  const l = lockLabel(lock);
  const cls = l.tone === "bad" ? "text-loss font-semibold" : l.tone === "warn" ? "text-warn" : "text-ink";
  return (
    <>
      <Field label="Scan lock" value={<span className={cls}>{l.text}</span>} />
      {lock.locked && (
        <>
          <Field label="Heartbeat" value={`${seconds(lock.heartbeat_age_seconds)} ago`} />
          {showOwner && (
            <Field
              label="Owner"
              value={
                <span className="block max-w-[14rem] truncate text-xs text-ink-2" title={lock.owner ?? ""}>
                  {lock.owner}
                </span>
              }
            />
          )}
        </>
      )}
    </>
  );
}

export { seconds as fmtSeconds };

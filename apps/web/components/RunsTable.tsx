import { dt } from "@/lib/format";
import type { CollectorRun } from "@/lib/types";
import { Empty, td, th } from "./ui";

export default function RunsTable({ runs }: { runs: CollectorRun[] }) {
  if (!runs.length) return <Empty>No runs recorded.</Empty>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px]">
        <thead className="border-b border-zinc-200 dark:border-zinc-800">
          <tr>
            <th className={th}>Started</th>
            <th className={th}>Source</th>
            <th className={th}>Result</th>
            <th className={`${th} text-right`}>Duration</th>
            <th className={`${th} text-right`}>Fetched</th>
            <th className={`${th} text-right`}>Matched</th>
            <th className={`${th} text-right`}>Evaluated</th>
            <th className={`${th} text-right`}>Deals</th>
            <th className={`${th} text-right`}>Alerts</th>
            <th className={th}>Notes / error</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id} className="border-b border-zinc-100 dark:border-zinc-900">
              <td className={`${td} whitespace-nowrap`}>{dt(r.started_at)}</td>
              <td className={td}>{r.source}</td>
              <td className={td}>{r.success ? <span className="text-emerald-600">ok</span> : <span className="text-red-600">failed</span>}</td>
              <td className={`${td} text-right tabular-nums`}>{r.duration_ms !== null ? `${(r.duration_ms / 1000).toFixed(1)} s` : "—"}</td>
              <td className={`${td} text-right tabular-nums`}>{r.items_fetched}</td>
              <td className={`${td} text-right tabular-nums`}>{r.items_matched}</td>
              <td className={`${td} text-right tabular-nums`}>{r.listings_evaluated}</td>
              <td className={`${td} text-right tabular-nums`}>{r.deals_found}</td>
              <td className={`${td} text-right tabular-nums`}>{r.alerts_sent}</td>
              <td className={`${td} max-w-xs break-words text-xs text-zinc-500`}>{r.error ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

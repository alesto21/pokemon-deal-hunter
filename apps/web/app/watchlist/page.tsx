"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import EntitySearch, { type EntityPick } from "@/components/EntitySearch";
import { Empty, ErrorBox, Loading, PageHeader, Panel, btnDanger, btnPrimary, input, td, th } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { nok } from "@/lib/format";
import type { WatchlistItem } from "@/lib/types";

export default function WatchlistPage() {
  const { data, error, loading, reload } = useApi<WatchlistItem[]>("watchlist");
  const [pick, setPick] = useState<EntityPick | null>(null);
  const [target, setTarget] = useState("");
  const [priority, setPriority] = useState("normal");
  const [notes, setNotes] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  async function run(fn: () => Promise<unknown>) {
    setActionError(null);
    try {
      await fn();
      reload();
    } catch (e) {
      setActionError((e as Error).message);
    }
  }

  function add(e: FormEvent) {
    e.preventDefault();
    if (!pick) return;
    run(async () => {
      await api("watchlist", {
        method: "POST",
        json: {
          entity_id: pick.entity_id,
          target_type: pick.entity_type,
          target_buy_price: target ? Number(target) : null,
          priority,
          notes: notes || null,
        },
      });
      setPick(null);
      setTarget("");
      setNotes("");
    });
  }

  return (
    <>
      <PageHeader title="Watchlist" subtitle="Cards and products you want to buy. Watchlisted items are always evaluated and get a bonus when at/below target." />
      <ErrorBox error={error ?? actionError} />
      <Panel title="Add to watchlist" className="mb-6">
        <form onSubmit={add} className="grid gap-2 md:grid-cols-6">
          <div className="md:col-span-2">
            {pick ? (
              <div className="flex items-center justify-between rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700">
                <span>{pick.label}</span>
                <button type="button" className="text-xs text-zinc-500" onClick={() => setPick(null)}>change</button>
              </div>
            ) : (
              <EntitySearch onPick={setPick} />
            )}
          </div>
          <input className={input} type="number" min="0" step="any" placeholder="Target buy NOK" value={target} onChange={(e) => setTarget(e.target.value)} />
          <select className={input} value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="high">High priority</option>
            <option value="normal">Normal</option>
            <option value="low">Low</option>
          </select>
          <input className={input} placeholder="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
          <button className={btnPrimary} disabled={!pick}>Add</button>
        </form>
      </Panel>
      <Panel>
        <Loading show={loading && !data} />
        {data && data.length === 0 && <Empty>Watchlist is empty.</Empty>}
        {data && data.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px]">
              <thead className="border-b border-zinc-200 dark:border-zinc-800">
                <tr>
                  <th className={th}>Item</th>
                  <th className={`${th} text-right`}>Target</th>
                  <th className={`${th} text-right`}>Fair value</th>
                  <th className={th}>Priority</th>
                  <th className={th}>Enabled</th>
                  <th className={th}></th>
                </tr>
              </thead>
              <tbody>
                {data.map((w) => (
                  <tr key={w.id} className="border-b border-zinc-100 dark:border-zinc-900">
                    <td className={td}>
                      <Link className="hover:underline" href={`/prices?type=${w.target_type}&id=${w.entity_id}`}>
                        {w.label ?? `${w.target_type} #${w.entity_id}`}
                      </Link>
                      {w.notes && <div className="text-xs text-zinc-500">{w.notes}</div>}
                    </td>
                    <td className={`${td} text-right tabular-nums`}>{nok(w.target_buy_price)}</td>
                    <td className={`${td} text-right tabular-nums`}>
                      {nok(w.fair_value_nok)}
                      {w.target_buy_price && w.fair_value_nok && w.fair_value_nok <= w.target_buy_price && (
                        <div className="text-xs text-emerald-600">market at/below target</div>
                      )}
                    </td>
                    <td className={td}>
                      <select
                        className={input}
                        value={w.priority}
                        onChange={(e) => run(() => api(`watchlist/${w.id}`, { method: "PATCH", json: { priority: e.target.value } }))}
                      >
                        <option value="high">high</option>
                        <option value="normal">normal</option>
                        <option value="low">low</option>
                      </select>
                    </td>
                    <td className={td}>
                      <input
                        type="checkbox"
                        checked={w.enabled}
                        onChange={(e) => run(() => api(`watchlist/${w.id}`, { method: "PATCH", json: { enabled: e.target.checked } }))}
                      />
                    </td>
                    <td className={`${td} text-right`}>
                      <button className={btnDanger} onClick={() => run(() => api(`watchlist/${w.id}`, { method: "DELETE" }))}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}

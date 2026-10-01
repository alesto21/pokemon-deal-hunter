"use client";

import { Eye, Plus, X } from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";
import EntitySearch, { type EntityPick } from "@/components/EntitySearch";
import WatchCard from "@/components/market/WatchCard";
import { EmptyState, ErrorBox, KpiCard, Loading, PageHeader, Panel, btn, btnGhost, btnPrimary, input } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import type { WatchRow } from "@/lib/dashboard";
import { pct } from "@/lib/format";

type Sort = "opportunity" | "fair_value" | "name" | "priority";
const PRIORITY_RANK = { high: 0, normal: 1, low: 2 } as const;

function AddForm({ onAdded }: { onAdded: () => void }) {
  const [pick, setPick] = useState<EntityPick | null>(null);
  const [target, setTarget] = useState("");
  const [priority, setPriority] = useState("normal");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function add(e: FormEvent) {
    e.preventDefault();
    if (!pick) return;
    setError(null);
    try {
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
      onAdded();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form onSubmit={add} className="space-y-2">
      <ErrorBox error={error} />
      <div className="grid gap-2 md:grid-cols-6">
        <div className="md:col-span-2">
          {pick ? (
            <div className="flex items-center justify-between rounded-lg border border-line bg-surface-2 px-2.5 py-1.5 text-sm">
              <span className="truncate">{pick.label}</span>
              <button type="button" className="text-xs text-ink-3 hover:text-ink" onClick={() => setPick(null)}>
                change
              </button>
            </div>
          ) : (
            <EntitySearch onPick={setPick} />
          )}
        </div>
        <input className={input} type="number" min="0" step="any" placeholder="Target buy NOK" value={target} onChange={(e) => setTarget(e.target.value)} />
        <select className={input} value={priority} onChange={(e) => setPriority(e.target.value)} aria-label="Priority">
          <option value="high">High priority</option>
          <option value="normal">Normal</option>
          <option value="low">Low</option>
        </select>
        <input className={input} placeholder="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
        <button className={btnPrimary} disabled={!pick}>
          Add
        </button>
      </div>
      <p className="text-xs text-ink-3">Watchlisted items are always evaluated and get a score bonus when a listing is at or below target.</p>
    </form>
  );
}

export default function WatchlistPage() {
  const { data, error, loading, reload } = useApi<{ items: WatchRow[] }>("dashboard/watchlist");
  const [actionError, setActionError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [sort, setSort] = useState<Sort>("opportunity");
  const [pokemon, setPokemon] = useState("");
  const [setName, setSetName] = useState("");
  const [priority, setPriority] = useState("");
  const [minFv, setMinFv] = useState("");
  const [maxFv, setMaxFv] = useState("");

  const items = useMemo(() => data?.items ?? [], [data]);
  const sets = useMemo(() => [...new Set(items.map((w) => w.entity?.set_name).filter(Boolean) as string[])].sort(), [items]);

  const visible = useMemo(() => {
    const q = pokemon.trim().toLowerCase();
    const rows = items.filter((w) => {
      const e = w.entity;
      if (q && !`${e?.pokemon ?? ""} ${e?.name ?? ""}`.toLowerCase().includes(q)) return false;
      if (setName && e?.set_name !== setName) return false;
      if (priority && w.priority !== priority) return false;
      if (minFv && (w.fair_value_nok ?? 0) < Number(minFv)) return false;
      if (maxFv && (w.fair_value_nok ?? Infinity) > Number(maxFv)) return false;
      return true;
    });
    const by: Record<Sort, (a: WatchRow, b: WatchRow) => number> = {
      opportunity: (a, b) => (b.best_discount_pct ?? -Infinity) - (a.best_discount_pct ?? -Infinity),
      fair_value: (a, b) => (b.fair_value_nok ?? 0) - (a.fair_value_nok ?? 0),
      name: (a, b) => (a.entity?.name ?? "").localeCompare(b.entity?.name ?? ""),
      priority: (a, b) => PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority],
    };
    return [...rows].sort((a, b) => (a.below_target === b.below_target ? by[sort](a, b) : a.below_target ? -1 : 1));
  }, [items, pokemon, setName, priority, minFv, maxFv, sort]);

  async function run(fn: () => Promise<unknown>) {
    setActionError(null);
    try {
      await fn();
      reload();
    } catch (e) {
      setActionError((e as Error).message);
    }
  }

  const belowTarget = items.filter((w) => w.below_target).length;
  const positive = items.filter((w) => (w.best_discount_pct ?? 0) > 0).length;
  const bestOpp = items.reduce<number | null>((m, w) => (w.best_discount_pct !== null && (m === null || w.best_discount_pct > m) ? w.best_discount_pct : m), null);
  const filtered = pokemon || setName || priority || minFv || maxFv;

  return (
    <>
      <PageHeader
        title="Watchlist"
        icon={Eye}
        subtitle="Cards and products you want to own, with today's market and the best listing for each."
        actions={
          <button className={showAdd ? btn : btnPrimary} onClick={() => setShowAdd((s) => !s)}>
            {showAdd ? <X size={15} /> : <Plus size={15} />} {showAdd ? "Close" : "Add target"}
          </button>
        }
      />
      <ErrorBox error={error ?? actionError} />
      {showAdd && (
        <Panel title="Add to watchlist" className="mb-6">
          <AddForm
            onAdded={() => {
              reload();
              setShowAdd(false);
            }}
          />
        </Panel>
      )}
      <Loading show={loading && !data} />
      {data && (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4 [&>*]:min-w-0">
            <KpiCard label="Targets" value={items.length} hint={`${items.filter((w) => w.priority === "high").length} high priority`} icon={Eye} />
            <KpiCard label="At / below target" value={belowTarget} tone={belowTarget ? "gold" : null} hint="landed cost ≤ your target" />
            <KpiCard label="Below fair value" value={positive} hint="best listing cheaper than fair value" />
            <KpiCard label="Best opportunity" value={bestOpp === null ? "—" : pct(bestOpp)} tone={bestOpp !== null && bestOpp > 0 ? "gain" : null} hint="best listing vs fair value" />
          </div>

          {items.length > 0 && (
            <div className="mb-4 grid grid-cols-2 gap-2 rounded-xl border border-line bg-surface p-3 sm:flex sm:flex-wrap sm:items-center">
              <select className={`${input} col-span-2 sm:w-48`} value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label="Sort">
                <option value="opportunity">Sort: best opportunity</option>
                <option value="fair_value">Sort: fair value</option>
                <option value="priority">Sort: priority</option>
                <option value="name">Sort: name</option>
              </select>
              <input className={`${input} sm:w-40`} placeholder="Pokémon" value={pokemon} onChange={(e) => setPokemon(e.target.value)} />
              <select className={`${input} sm:w-48`} value={setName} onChange={(e) => setSetName(e.target.value)} aria-label="Set">
                <option value="">All sets</option>
                {sets.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <select className={`${input} sm:w-36`} value={priority} onChange={(e) => setPriority(e.target.value)} aria-label="Priority">
                <option value="">Any priority</option>
                <option value="high">High</option>
                <option value="normal">Normal</option>
                <option value="low">Low</option>
              </select>
              <input className={`${input} sm:w-32`} type="number" min="0" placeholder="Min fair NOK" value={minFv} onChange={(e) => setMinFv(e.target.value)} />
              <input className={`${input} sm:w-32`} type="number" min="0" placeholder="Max fair NOK" value={maxFv} onChange={(e) => setMaxFv(e.target.value)} />
              {filtered && (
                <button
                  className={btnGhost}
                  onClick={() => {
                    setPokemon("");
                    setSetName("");
                    setPriority("");
                    setMinFv("");
                    setMaxFv("");
                  }}
                >
                  Reset
                </button>
              )}
            </div>
          )}

          {items.length === 0 ? (
            <Panel>
              <EmptyState
                icon={Eye}
                title="Your watchlist is empty"
                action={
                  <button className={btnPrimary} onClick={() => setShowAdd(true)}>
                    <Plus size={15} /> Add a target
                  </button>
                }
              >
                Add cards you want to own; they&apos;re always evaluated and flagged when a listing hits your target price.
              </EmptyState>
            </Panel>
          ) : visible.length === 0 ? (
            <Panel>
              <EmptyState icon={Eye} title="No targets match these filters" />
            </Panel>
          ) : (
            <div className="grid gap-3 lg:grid-cols-2 2xl:grid-cols-3 [&>*]:min-w-0">
              {visible.map((w) => (
                <WatchCard
                  key={w.id}
                  w={w}
                  onSave={(id, body) => run(() => api(`watchlist/${id}`, { method: "PATCH", json: body }))}
                  onRemove={(id) => run(() => api(`watchlist/${id}`, { method: "DELETE" }))}
                />
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}

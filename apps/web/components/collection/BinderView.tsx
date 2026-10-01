"use client";

import { LayoutGrid, List, type LucideIcon, RefreshCw, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { AddFirstCta, entityName, entitySub, GradingBadge, HoldingList, KindBadge, UnpricedNote } from "@/components/portfolio/common";
import {
  btnGhost,
  CardThumb,
  type Column,
  DataTable,
  Delta,
  EmptyState,
  ErrorBox,
  KpiCard,
  Loading,
  PageHeader,
  Panel,
  ProgressBar,
  Segmented,
  input,
} from "@/components/ui";
import { useApi } from "@/lib/api";
import type { Binder, HoldingRow } from "@/lib/dashboard";
import { day, nok, pct } from "@/lib/format";
import { SlotMap } from "./SlotMap";

type Sort = "value" | "gain" | "name" | "set" | "added";

const SORTS: Record<Sort, (a: HoldingRow, b: HoldingRow) => number> = {
  value: (a, b) => b.value_nok - a.value_nok,
  gain: (a, b) => (b.gain_pct ?? -Infinity) - (a.gain_pct ?? -Infinity),
  name: (a, b) => (a.entity?.name ?? "").localeCompare(b.entity?.name ?? ""),
  set: (a, b) => (a.entity?.set_name ?? "").localeCompare(b.entity?.set_name ?? "") || (a.entity?.number ?? "").localeCompare(b.entity?.number ?? "", undefined, { numeric: true }),
  added: (a, b) => b.added_at.localeCompare(a.added_at),
};

function CardTile({ h }: { h: HoldingRow }) {
  const e = h.entity;
  return (
    <div className="flex flex-col rounded-xl border border-line bg-surface-2 p-2.5">
      <div className="relative">
        <CardThumb src={e?.image_url} alt={e?.name ?? ""} size="lg" className="aspect-[5/7] h-auto! w-full!" />
        {h.quantity > 1 && (
          <span className="num absolute right-1.5 top-1.5 rounded-md bg-canvas/85 px-1.5 py-0.5 text-[11px] text-ink">×{h.quantity}</span>
        )}
      </div>
      <div className="mt-2 min-w-0">
        <div className="truncate text-sm font-medium text-ink" title={e?.name}>{e?.name ?? "Unknown"}</div>
        <div className="truncate text-xs text-ink-3">
          {e?.number} · {e?.set_name}
        </div>
      </div>
      <div className="mt-2 space-y-0.5 text-xs">
        <div className="flex justify-between text-ink-3">
          <span>Paid</span>
          <span className="num">{nok(h.acquisition_price_nok)}</span>
        </div>
        <div className="flex justify-between text-ink-3">
          <span>Value</span>
          <span className="num text-ink">{h.value_priced ? nok(h.unit_value_nok) : "No price"}</span>
        </div>
        <div className="flex justify-between text-ink-3">
          <span>P/L</span>
          <Delta pctValue={h.gain_pct} />
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        <KindBadge kind={h.kind} />
        {h.grading_status !== "raw" && <GradingBadge status={h.grading_status} company={h.grade_company} grade={h.grade} />}
      </div>
    </div>
  );
}

function EmptyTile() {
  return (
    <div className="grid min-h-40 place-items-center rounded-xl border border-dashed border-line text-[11px] text-ink-3">
      empty
    </div>
  );
}

const COLUMNS: Column<HoldingRow>[] = [
  {
    key: "card",
    header: "Card",
    cell: (h) => (
      <div className="flex items-center gap-3">
        <CardThumb src={h.entity?.image_url} alt={h.entity?.name ?? ""} size="sm" />
        <div className="min-w-0">
          <div className="truncate text-ink">
            {entityName(h.entity)}
            {h.quantity > 1 && <span className="ml-1 text-ink-3">×{h.quantity}</span>}
          </div>
          <div className="truncate text-xs text-ink-3">{entitySub(h.entity)}</div>
        </div>
      </div>
    ),
  },
  {
    key: "status",
    header: "Status",
    hideBelow: "lg",
    cell: (h) => (
      <div className="flex flex-wrap gap-1">
        <KindBadge kind={h.kind} />
        {h.grading_status !== "raw" && <GradingBadge status={h.grading_status} company={h.grade_company} grade={h.grade} />}
      </div>
    ),
  },
  { key: "paid", header: "Paid", align: "right", cell: (h) => nok(h.acquisition_price_nok) },
  { key: "value", header: "Fair value", align: "right", cell: (h) => (h.value_priced ? nok(h.unit_value_nok) : <span className="text-ink-3">No price</span>) },
  { key: "gain", header: "P/L", align: "right", cell: (h) => <Delta nokValue={h.gain_nok} pctValue={h.gain_pct} /> },
  { key: "added", header: "Added", align: "right", hideBelow: "xl", cell: (h) => <span className="text-ink-3">{day(h.acquisition_date ?? h.added_at)}</span> },
];

function mobileRow(h: HoldingRow) {
  return (
    <div className="flex items-center gap-3">
      <CardThumb src={h.entity?.image_url} alt={h.entity?.name ?? ""} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm text-ink">{entityName(h.entity)}</div>
        <div className="truncate text-xs text-ink-3">{h.entity?.set_name}</div>
        <div className="mt-1 flex flex-wrap gap-1">
          <KindBadge kind={h.kind} />
          {h.grading_status !== "raw" && <GradingBadge status={h.grading_status} company={h.grade_company} grade={h.grade} />}
        </div>
      </div>
      <div className="shrink-0 text-right text-xs">
        <div className="num text-sm text-ink">{h.value_priced ? nok(h.value_nok) : "No price"}</div>
        <div className="num text-ink-3">paid {nok(h.cost_nok)}</div>
        <Delta pctValue={h.gain_pct} />
      </div>
    </div>
  );
}

export default function BinderView({
  binderType,
  title,
  subtitle,
  icon,
}: {
  binderType: "premium" | "regular";
  title: string;
  subtitle: string;
  icon: LucideIcon;
}) {
  const { data, error, loading, reload } = useApi<Binder>(`dashboard/binder/${binderType}`);
  const [view, setView] = useState<"grid" | "list">("grid");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<Sort>("value");
  const [pokemon, setPokemon] = useState("");
  const [setName, setSetName] = useState("");
  const [grading, setGrading] = useState("");
  const [minV, setMinV] = useState("");
  const [maxV, setMaxV] = useState("");

  const items = useMemo(() => data?.items ?? [], [data]);
  const pokemonOptions = useMemo(() => [...new Set(items.map((h) => h.entity?.pokemon).filter(Boolean) as string[])].sort(), [items]);
  const setOptions = useMemo(() => [...new Set(items.map((h) => h.entity?.set_name).filter(Boolean) as string[])].sort(), [items]);

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return items
      .filter((h) => !needle || `${h.entity?.name} ${h.entity?.number} ${h.entity?.set_name}`.toLowerCase().includes(needle))
      .filter((h) => !pokemon || h.entity?.pokemon === pokemon)
      .filter((h) => !setName || h.entity?.set_name === setName)
      .filter((h) => !grading || h.grading_status === grading)
      .filter((h) => !minV || (h.unit_value_nok ?? 0) >= Number(minV))
      .filter((h) => !maxV || (h.unit_value_nok ?? 0) <= Number(maxV))
      .sort(SORTS[sort]);
  }, [items, q, pokemon, setName, grading, minV, maxV, sort]);

  const s = data?.summary;
  const empty = data && data.slots_used === 0;
  const graded = items.filter((h) => h.kind === "graded").reduce((n, h) => n + h.quantity, 0);
  const filtered = rows.length !== items.length;

  return (
    <>
      <PageHeader
        title={title}
        subtitle={subtitle}
        icon={icon}
        actions={
          <button className={btnGhost} onClick={reload} disabled={loading}>
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        }
      />
      <ErrorBox error={error} />
      <Loading show={loading && !data} />
      {data && s && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
            <Panel className="lg:col-span-3" title="Binder progress" subtitle={`${data.capacity} pockets`}>
              <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
                <div className="num text-3xl font-semibold text-ink">
                  {data.slots_used}
                  <span className="text-lg font-normal text-ink-3"> / {data.capacity}</span>
                </div>
                <div className="text-right text-sm text-ink-3">
                  <span className="num text-ink">{pct(data.pct_complete, 1)}</span> complete · {data.slots_free} free
                </div>
              </div>
              <ProgressBar value={data.pct_complete} />
              <div className="mt-4">
                <SlotMap capacity={data.capacity} used={data.slots_used} graded={graded} />
              </div>
            </Panel>
            <div className="grid auto-rows-min grid-cols-2 content-start gap-3 lg:col-span-2">
              <KpiCard label="Binder value" tone={empty ? null : "gold"} value={empty ? "—" : nok(s.value_nok)} hint={empty ? "No cards yet" : "current fair value"} />
              <KpiCard label="Cost" value={empty ? "—" : nok(s.cost_nok)} hint="acquisition" />
              <KpiCard label="Unrealised P/L" tone={empty ? null : s.gain_nok > 0 ? "gain" : s.gain_nok < 0 ? "loss" : null}
                value={empty ? "—" : `${s.gain_nok > 0 ? "+" : ""}${nok(s.gain_nok)}`} hint={s.gain_pct !== null ? pct(s.gain_pct, 1, true) : "—"} />
              <KpiCard label="Avg card value" value={s.avg_card_value_nok !== null ? nok(s.avg_card_value_nok) : "—"} hint={`${data.sets.length} set${data.sets.length === 1 ? "" : "s"}`} />
            </div>
          </div>
          <UnpricedNote count={s.unpriced} />

          {empty ? (
            <Panel>
              <EmptyState icon={icon} title={`Your ${title} is empty`} action={<AddFirstCta label="Add a card" />}>
                Add a card to the portfolio with binder “{binderType === "premium" ? "premium" : "regular"}” and it appears here with live values.
              </EmptyState>
            </Panel>
          ) : (
            <>
              {binderType === "regular" && (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  <Panel title="Sets represented" bodyClassName="px-4 py-2">
                    <div className="divide-y divide-line/70">
                      {data.sets.map((st) => (
                        <div key={st.set_name} className="flex justify-between py-1.5 text-sm">
                          <span className="truncate text-ink-2">{st.set_name}</span>
                          <span className="num text-ink-3">{st.cards}</span>
                        </div>
                      ))}
                    </div>
                  </Panel>
                  <Panel title="Top cards" bodyClassName="px-4 py-1">
                    <HoldingList rows={data.top_cards} empty="No priced cards yet." />
                  </Panel>
                  <Panel title="Recent additions" bodyClassName="px-4 py-1">
                    <HoldingList rows={data.recent_additions} empty="Nothing added yet."
                      right={(h) => <span className="text-xs text-ink-3">{day(h.acquisition_date ?? h.added_at)}</span>} />
                  </Panel>
                </div>
              )}

              <Panel
                title={`Cards${filtered ? ` · ${rows.length} of ${items.length}` : ` · ${items.length}`}`}
                actions={
                  <Segmented value={view} onChange={setView}
                    options={[{ value: "grid", label: <span className="flex items-center gap-1"><LayoutGrid size={13} /> Grid</span> },
                      { value: "list", label: <span className="flex items-center gap-1"><List size={13} /> List</span> }]} />
                }
              >
                <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8">
                  <div className="relative col-span-2">
                    <Search size={14} className="pointer-events-none absolute left-2.5 top-2.5 text-ink-3" />
                    <input className={`${input} pl-8`} placeholder="Search name, number, set…" value={q} onChange={(e) => setQ(e.target.value)} />
                  </div>
                  <select className={input} value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label="Sort">
                    <option value="value">Sort: value</option>
                    <option value="gain">Sort: gain %</option>
                    <option value="name">Sort: name</option>
                    <option value="set">Sort: set & number</option>
                    <option value="added">Sort: recently added</option>
                  </select>
                  <select className={input} value={pokemon} onChange={(e) => setPokemon(e.target.value)} aria-label="Pokémon">
                    <option value="">All Pokémon</option>
                    {pokemonOptions.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                  <select className={input} value={setName} onChange={(e) => setSetName(e.target.value)} aria-label="Set">
                    <option value="">All sets</option>
                    {setOptions.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                  <select className={input} value={grading} onChange={(e) => setGrading(e.target.value)} aria-label="Grading status">
                    <option value="">Any grading status</option>
                    <option value="raw">Raw</option>
                    <option value="submitted">Submitted</option>
                    <option value="at_grader">At grader</option>
                    <option value="graded">Graded</option>
                  </select>
                  <div className="col-span-2 flex gap-2">
                    <input className={input} type="number" inputMode="numeric" placeholder="Min NOK" value={minV} onChange={(e) => setMinV(e.target.value)} aria-label="Minimum value" />
                    <input className={input} type="number" inputMode="numeric" placeholder="Max NOK" value={maxV} onChange={(e) => setMaxV(e.target.value)} aria-label="Maximum value" />
                  </div>
                </div>

                {rows.length === 0 ? (
                  <EmptyState title="No cards match these filters" />
                ) : view === "grid" ? (
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6">
                    {rows.map((h) => <CardTile key={h.id} h={h} />)}
                    {!filtered && Array.from({ length: Math.min(data.slots_free, 2) }, (_, i) => <EmptyTile key={`e${i}`} />)}
                  </div>
                ) : (
                  <DataTable rows={rows} columns={COLUMNS} rowKey={(h) => h.id} mobileCard={mobileRow} />
                )}
                {!filtered && view === "grid" && data.slots_free > 2 && (
                  <div className="mt-3 text-center text-xs text-ink-3">+ {data.slots_free - 2} more empty pockets</div>
                )}
              </Panel>
            </>
          )}
        </div>
      )}
    </>
  );
}

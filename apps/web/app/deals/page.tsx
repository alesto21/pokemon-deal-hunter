"use client";

import { Plus, SlidersHorizontal, Tag, X } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { AddFinnListing, ImportListings } from "@/components/deals/AddListingForms";
import DealDetailSheet from "@/components/deals/DealDetailSheet";
import DealList from "@/components/deals/DealList";
import { EmptyState, ErrorBox, Loading, PageHeader, Panel, btn, btnGhost, btnPrimary, input } from "@/components/ui";
import { qs, useApi } from "@/lib/api";
import type { DealsResponse } from "@/lib/dashboard";

const LEVELS = [
  { value: "STEAL", label: "Steal" },
  { value: "STRONG_BUY", label: "Strong buy" },
  { value: "GOOD", label: "Good" },
  { value: "WATCH", label: "Watch" },
  { value: "IGNORE", label: "Ignore" },
];
const DEFAULT_LEVELS = ["STEAL", "STRONG_BUY", "GOOD", "WATCH"];
const PAGE = 50;

interface Filters {
  levels: string[];
  source: string;
  seller_region: string;
  pokemon: string;
  set_code: string;
  min_landed: string;
  max_landed: string;
  min_discount: string; // percent
  min_confidence: string;
  min_score: string;
  q: string;
  sort: string;
  status: string;
}

const EMPTY: Filters = {
  levels: DEFAULT_LEVELS,
  source: "",
  seller_region: "",
  pokemon: "",
  set_code: "",
  min_landed: "",
  max_landed: "",
  min_discount: "",
  min_confidence: "",
  min_score: "",
  q: "",
  sort: "score",
  status: "active",
};

function activeCount(f: Filters): number {
  const keys: (keyof Filters)[] = ["source", "seller_region", "pokemon", "set_code", "min_landed", "max_landed", "min_discount", "min_confidence", "min_score"];
  return keys.filter((k) => f[k] !== "").length + (f.status !== "active" ? 1 : 0);
}

function DealsView() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const openId = params.get("listing") ? Number(params.get("listing")) : null;

  const [f, setF] = useState<Filters>(EMPTY);
  const [applied, setApplied] = useState<Filters>(EMPTY);
  const [pages, setPages] = useState(1);
  const [showMore, setShowMore] = useState(false);
  const [showAdd, setShowAdd] = useState(false);

  // Debounce typing; chips/selects still feel instant at 250 ms.
  useEffect(() => {
    const t = setTimeout(() => {
      setApplied(f);
      setPages(1);
    }, 250);
    return () => clearTimeout(t);
  }, [f]);

  const path = useMemo(
    () =>
      `dashboard/deals${qs({
        level: applied.levels.length === LEVELS.length ? undefined : applied.levels,
        source: applied.source,
        seller_region: applied.seller_region,
        pokemon: applied.pokemon,
        set_code: applied.set_code.toUpperCase(),
        min_landed: applied.min_landed,
        max_landed: applied.max_landed,
        min_discount: applied.min_discount ? String(Number(applied.min_discount) / 100) : undefined,
        min_confidence: applied.min_confidence,
        min_score: applied.min_score,
        q: applied.q,
        sort: applied.sort,
        status: applied.status,
        limit: PAGE * pages,
      })}`,
    [applied, pages],
  );
  const { data, error, loading, reload } = useApi<DealsResponse>(applied.levels.length ? path : null);

  const setOpen = useCallback(
    (id: number | null) => {
      const sp = new URLSearchParams(params.toString());
      if (id === null) sp.delete("listing");
      else sp.set("listing", String(id));
      const s = sp.toString();
      router.replace(s ? `${pathname}?${s}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );
  const closeDetail = useCallback(() => setOpen(null), [setOpen]);

  const set = (k: keyof Filters) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const toggleLevel = (lv: string) =>
    setF({ ...f, levels: f.levels.includes(lv) ? f.levels.filter((x) => x !== lv) : [...f.levels, lv] });
  const extra = activeCount(f);

  return (
    <>
      <PageHeader
        title="Deals"
        icon={Tag}
        subtitle="Evaluated listings ranked by effective level (after caps). Prices are landed cost: item + shipping + import buffer."
        actions={
          <button className={showAdd ? btn : btnPrimary} onClick={() => setShowAdd((s) => !s)}>
            {showAdd ? <X size={15} /> : <Plus size={15} />} {showAdd ? "Close" : "Add FINN listing"}
          </button>
        }
      />

      {showAdd && (
        <div className="mb-6 grid gap-4 lg:grid-cols-2">
          <Panel title="Add a FINN listing" subtitle="Paste a URL you found; it is evaluated immediately.">
            <AddFinnListing
              onDone={(id) => {
                reload();
                setOpen(id);
              }}
            />
          </Panel>
          <Panel title="Import CSV / JSON" subtitle="Bulk-add listing URLs.">
            <ImportListings onDone={reload} />
          </Panel>
        </div>
      )}

      {/* Filters */}
      <div className="mb-4 space-y-3 rounded-xl border border-line bg-surface p-3">
        <div className="flex flex-wrap items-center gap-2">
          <input className={`${input} sm:w-auto sm:min-w-0 sm:flex-1`} placeholder="Search listing title…" value={f.q} onChange={set("q")} />
          <select className={`${input} sm:w-48`} value={f.sort} onChange={set("sort")} aria-label="Sort">
            <option value="score">Sort: score</option>
            <option value="discount">Sort: discount</option>
            <option value="landed">Sort: lowest landed</option>
            <option value="newest">Sort: newest</option>
          </select>
          <button className={btnGhost} onClick={() => setShowMore((s) => !s)} aria-expanded={showMore}>
            <SlidersHorizontal size={15} /> Filters{extra ? ` (${extra})` : ""}
          </button>
          {(extra > 0 || f.q || f.levels.join() !== DEFAULT_LEVELS.join()) && (
            <button className={btnGhost} onClick={() => setF(EMPTY)}>
              Reset
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {LEVELS.map((l) => {
            const on = f.levels.includes(l.value);
            return (
              <button
                key={l.value}
                onClick={() => toggleLevel(l.value)}
                aria-pressed={on}
                className={`rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset ${
                  on ? "bg-surface-3 text-ink ring-line-strong" : "text-ink-3 ring-line hover:text-ink-2"
                }`}
              >
                {l.label}
              </button>
            );
          })}
        </div>
        {showMore && (
          <div className="grid grid-cols-2 gap-2 border-t border-line pt-3 md:grid-cols-3 xl:grid-cols-5">
            <select className={input} value={f.source} onChange={set("source")} aria-label="Source">
              <option value="">Any source</option>
              <option value="cardtrader">CardTrader</option>
              <option value="finn">FINN</option>
              <option value="manual">Manual</option>
            </select>
            <select className={input} value={f.seller_region} onChange={set("seller_region")} aria-label="Seller region">
              <option value="">Any seller region</option>
              <option value="EEA">EEA</option>
              <option value="UK">UK</option>
              <option value="Switzerland">Switzerland</option>
              <option value="US">US</option>
              <option value="Canada">Canada</option>
              <option value="other">Other / unknown</option>
            </select>
            <input className={input} placeholder="Pokémon" value={f.pokemon} onChange={set("pokemon")} />
            <input className={input} placeholder="Set code (e.g. TEF)" value={f.set_code} onChange={set("set_code")} />
            <select className={input} value={f.status} onChange={set("status")} aria-label="Listing status">
              <option value="active">Active listings</option>
              <option value="gone">Gone</option>
              <option value="sold">Sold</option>
              <option value="ignored">Ignored</option>
              <option value="all">All</option>
            </select>
            <input className={input} type="number" min="0" placeholder="Min landed NOK" value={f.min_landed} onChange={set("min_landed")} />
            <input className={input} type="number" min="0" placeholder="Max landed NOK" value={f.max_landed} onChange={set("max_landed")} />
            <input className={input} type="number" placeholder="Min discount %" value={f.min_discount} onChange={set("min_discount")} />
            <select className={input} value={f.min_confidence} onChange={set("min_confidence")} aria-label="Minimum confidence">
              <option value="">Any confidence</option>
              <option value="0.5">Confidence ≥ 50%</option>
              <option value="0.7">Confidence ≥ 70%</option>
              <option value="0.9">Confidence ≥ 90%</option>
            </select>
            <input className={input} type="number" min="0" max="100" placeholder="Min raw score" value={f.min_score} onChange={set("min_score")} />
          </div>
        )}
      </div>

      <ErrorBox error={error} />
      {!applied.levels.length ? (
        <Panel>
          <EmptyState icon={Tag} title="No levels selected">
            Pick at least one recommendation level.
          </EmptyState>
        </Panel>
      ) : (
        <>
          <Loading show={loading && !data} />
          {data && (
            <Panel
              title={`${data.total.toLocaleString("nb-NO")} listing${data.total === 1 ? "" : "s"}`}
              subtitle="Select a row for the full price / market / decision breakdown."
              bodyClassName="p-2 sm:p-3"
            >
              {data.items.length ? (
                <DealList items={data.items} onOpen={(id) => setOpen(id)} />
              ) : (
                <EmptyState icon={Tag} title="No deals match these filters">
                  Deals appear as CardTrader scans run and FINN listings are added. Try widening the levels or clearing filters.
                </EmptyState>
              )}
              {data.items.length < data.total && (
                <div className="mt-3 text-center">
                  <button className={btn} onClick={() => setPages((p) => p + 1)} disabled={loading}>
                    {loading ? "Loading…" : `Show more (${data.total - data.items.length} left)`}
                  </button>
                </div>
              )}
            </Panel>
          )}
        </>
      )}

      {openId !== null && !Number.isNaN(openId) && <DealDetailSheet listingId={openId} onClose={closeDetail} />}
    </>
  );
}

export default function DealsPage() {
  return (
    <Suspense fallback={<Loading />}>
      <DealsView />
    </Suspense>
  );
}

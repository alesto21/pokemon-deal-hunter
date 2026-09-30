"use client";

import { useMemo, useState } from "react";
import { AddFinnListing, ImportListings } from "@/components/AddListingForms";
import DealsTable from "@/components/DealsTable";
import { ErrorBox, Loading, PageHeader, Panel, btn, input } from "@/components/ui";
import { qs, useApi } from "@/lib/api";
import type { DealsResponse } from "@/lib/types";

const RECS = ["STEAL", "STRONG_BUY", "GOOD", "WATCH", "IGNORE"];

export default function DealsPage() {
  const [f, setF] = useState({
    source: "",
    seller_region: "",
    min_score: "",
    binder_fit: "",
    min_price: "",
    max_price: "",
    q: "",
    status: "active",
  });
  const [recs, setRecs] = useState<string[]>(["STEAL", "STRONG_BUY", "GOOD", "WATCH"]);
  const [showAdd, setShowAdd] = useState(false);

  const path = useMemo(
    () =>
      `deals${qs({
        source: f.source,
        min_score: f.min_score,
        binder_fit: f.binder_fit,
        seller_region: f.seller_region,
        min_price: f.min_price,
        max_price: f.max_price,
        q: f.q,
        status: f.status,
        recommendation: recs.length === RECS.length ? undefined : recs,
        limit: 200,
      })}`,
    [f, recs],
  );
  const { data, error, loading, reload } = useApi<DealsResponse>(path);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  return (
    <>
      <PageHeader
        title="Deals"
        subtitle="Latest evaluation per listing. Click a row for the reasoning."
        actions={
          <div className="flex gap-2">
            <button className={btn} onClick={() => setShowAdd((s) => !s)}>{showAdd ? "Hide" : "+ Add FINN listing"}</button>
            <button className={btn} onClick={reload}>Refresh</button>
          </div>
        }
      />
      {showAdd && (
        <div className="mb-6 grid gap-6 lg:grid-cols-2">
          <Panel title="Add FINN listing by URL"><AddFinnListing onDone={reload} /></Panel>
          <Panel title="Import CSV / JSON"><ImportListings onDone={reload} /></Panel>
        </div>
      )}
      <Panel className="mb-6">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
          <input className={`${input} col-span-2`} placeholder="Search title…" value={f.q} onChange={set("q")} />
          <select className={input} value={f.source} onChange={set("source")}>
            <option value="">All sources</option>
            <option value="cardtrader">CardTrader</option>
            <option value="finn">FINN</option>
            <option value="manual">Manual</option>
          </select>
          <select className={input} value={f.seller_region} onChange={set("seller_region")}>
            <option value="">Any seller region</option>
            <option value="EEA">EEA</option>
            <option value="UK">UK</option>
            <option value="Switzerland">Switzerland</option>
            <option value="US">US</option>
            <option value="Canada">Canada</option>
            <option value="other">Other / unknown</option>
          </select>
          <select className={input} value={f.binder_fit} onChange={set("binder_fit")}>
            <option value="">Any binder fit</option>
            <option value="premium">Premium</option>
            <option value="regular">Regular</option>
            <option value="graded">Graded</option>
            <option value="sealed">Sealed</option>
            <option value="none">None</option>
          </select>
          <input className={input} type="number" placeholder="Min score" value={f.min_score} onChange={set("min_score")} />
          <input className={input} type="number" placeholder="Min landed NOK" value={f.min_price} onChange={set("min_price")} />
          <input className={input} type="number" placeholder="Max landed NOK" value={f.max_price} onChange={set("max_price")} />
          <select className={input} value={f.status} onChange={set("status")}>
            <option value="active">Active</option>
            <option value="gone">Gone</option>
            <option value="sold">Sold</option>
            <option value="ignored">Ignored</option>
            <option value="all">All</option>
          </select>
        </div>
        <div className="mt-3 flex flex-wrap gap-3 text-sm">
          {RECS.map((r) => (
            <label key={r} className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={recs.includes(r)}
                onChange={(e) => setRecs(e.target.checked ? [...recs, r] : recs.filter((x) => x !== r))}
              />
              {r.replace("_", " ")}
            </label>
          ))}
        </div>
      </Panel>
      <ErrorBox error={error} />
      <Panel title={data ? `${data.total} listing(s)` : "Listings"}>
        <Loading show={loading && !data} />
        {data && <DealsTable items={data.items} />}
      </Panel>
    </>
  );
}

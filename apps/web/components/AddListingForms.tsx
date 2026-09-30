"use client";

import { useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import type { ImportResult, Listing } from "@/lib/types";
import { nok, num } from "@/lib/format";
import { ErrorBox, RecBadge, btn, btnPrimary, input } from "./ui";

export function AddFinnListing({ onDone }: { onDone: () => void }) {
  const [form, setForm] = useState({ url: "", title: "", price: "", shipping_nok: "", condition: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Listing | null>(null);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = { url: form.url.trim() };
      if (form.title.trim()) body.title = form.title.trim();
      if (form.price) body.price = Number(form.price);
      if (form.shipping_nok) body.shipping_nok = Number(form.shipping_nok);
      if (form.condition.trim()) body.condition = form.condition.trim();
      const l = await api<Listing>("listings/manual", { method: "POST", json: body });
      setResult(l);
      setForm({ url: "", title: "", price: "", shipping_nok: "", condition: "" });
      onDone();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-2">
      <ErrorBox error={error} />
      <input className={input} required placeholder="https://www.finn.no/…" value={form.url} onChange={set("url")} />
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <input className={input} placeholder="Title (optional)" value={form.title} onChange={set("title")} />
        <input className={input} type="number" min="0" step="any" placeholder="Price NOK" value={form.price} onChange={set("price")} />
        <input className={input} type="number" min="0" step="any" placeholder="Shipping NOK" value={form.shipping_nok} onChange={set("shipping_nok")} />
        <input className={input} placeholder="Condition" value={form.condition} onChange={set("condition")} />
      </div>
      <p className="text-xs text-zinc-500">
        Only listings you paste are added. If FINN&apos;s robots.txt allows it, one request reads the page metadata; otherwise supply title and price.
      </p>
      <button className={btnPrimary} disabled={busy}>{busy ? "Adding…" : "Add & evaluate"}</button>
      {result && (
        <div className="rounded-md border border-zinc-200 p-2 text-sm dark:border-zinc-800">
          Added <b>{result.entity_label ?? result.title}</b> — {nok(result.total_price_nok)} · score {num(result.evaluation?.total_score)}{" "}
          <RecBadge rec={result.evaluation?.alert_level} /> · match {result.match_status}
        </div>
      )}
    </form>
  );
}

export function ImportListings({ onDone }: { onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      setResult(await api<ImportResult>("listings/import", { method: "POST", body: fd }));
      onDone();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-2">
      <ErrorBox error={error} />
      <input type="file" accept=".csv,.json" className="text-sm" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      <p className="text-xs text-zinc-500">CSV columns: url,title,price,currency,shipping_nok,condition,description — or a JSON list of objects.</p>
      <button className={btn} disabled={busy || !file}>{busy ? "Importing…" : "Import"}</button>
      {result && (
        <div className="text-sm">
          Imported {result.imported}, failed {result.failed}.
          {result.errors.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-xs text-red-600">
              {result.errors.map((e) => <li key={e.row}>row {e.row}: {e.error}</li>)}
            </ul>
          )}
        </div>
      )}
    </form>
  );
}

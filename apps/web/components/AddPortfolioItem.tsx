"use client";

import { useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import EntitySearch, { type EntityPick } from "./EntitySearch";
import { ErrorBox, btnPrimary, input } from "./ui";

const EMPTY = {
  quantity: "1",
  acquisition_price_nok: "",
  acquisition_date: "",
  binder_type: "regular",
  condition: "Near Mint",
  grading_status: "raw",
  grade_company: "PSA",
  psa_grade: "",
  notes: "",
};

export default function AddPortfolioItem({ onDone }: { onDone: () => void }) {
  const [pick, setPick] = useState<EntityPick | null>(null);
  const [f, setF] = useState(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!pick) return;
    setBusy(true);
    setError(null);
    try {
      await api("portfolio", {
        method: "POST",
        json: {
          card_id: pick.entity_type === "card" ? pick.entity_id : null,
          product_id: pick.entity_type === "product" ? pick.entity_id : null,
          quantity: Number(f.quantity) || 1,
          acquisition_price_nok: Number(f.acquisition_price_nok) || 0,
          acquisition_date: f.acquisition_date || null,
          binder_type: f.binder_type,
          condition: f.condition || null,
          grading_status: f.grading_status,
          grade_company: f.grading_status === "graded" ? f.grade_company || "PSA" : null,
          psa_grade: f.grading_status === "graded" && f.psa_grade ? Number(f.psa_grade) : null,
          notes: f.notes || null,
        },
      });
      setPick(null);
      setF(EMPTY);
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
      {pick ? (
        <div className="flex items-center justify-between rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700">
          <span>{pick.label}</span>
          <button type="button" className="text-xs text-zinc-500" onClick={() => setPick(null)}>change</button>
        </div>
      ) : (
        <EntitySearch onPick={setPick} />
      )}
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <label className="text-xs text-zinc-500">Quantity<input className={input} type="number" min="1" value={f.quantity} onChange={set("quantity")} /></label>
        <label className="text-xs text-zinc-500">Price per unit (NOK)<input className={input} type="number" min="0" step="any" value={f.acquisition_price_nok} onChange={set("acquisition_price_nok")} /></label>
        <label className="text-xs text-zinc-500">Date<input className={input} type="date" value={f.acquisition_date} onChange={set("acquisition_date")} /></label>
        <label className="text-xs text-zinc-500">Binder
          <select className={input} value={f.binder_type} onChange={set("binder_type")}>
            <option value="regular">Regular</option>
            <option value="premium">Premium (GOD)</option>
            <option value="graded">Graded</option>
            <option value="sealed">Sealed</option>
          </select>
        </label>
        <label className="text-xs text-zinc-500">Condition<input className={input} value={f.condition} onChange={set("condition")} /></label>
        <label className="text-xs text-zinc-500">Grading
          <select className={input} value={f.grading_status} onChange={set("grading_status")}>
            <option value="raw">Raw</option>
            <option value="submitted">Submitted</option>
            <option value="graded">Graded</option>
          </select>
        </label>
        {f.grading_status === "graded" && (
          <>
            <label className="text-xs text-zinc-500">Company<input className={input} value={f.grade_company} onChange={set("grade_company")} /></label>
            <label className="text-xs text-zinc-500">Grade<input className={input} type="number" min="1" max="10" step="0.5" value={f.psa_grade} onChange={set("psa_grade")} /></label>
          </>
        )}
      </div>
      <input className={input} placeholder="Notes" value={f.notes} onChange={set("notes")} />
      <button className={btnPrimary} disabled={!pick || busy}>{busy ? "Saving…" : "Add to portfolio"}</button>
    </form>
  );
}

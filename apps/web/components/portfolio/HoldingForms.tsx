"use client";

import { Trash2, X } from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";
import EntitySearch, { type EntityPick } from "@/components/EntitySearch";
import { btn, btnDanger, btnPrimary, CardThumb, ErrorBox, input } from "@/components/ui";
import { api } from "@/lib/api";
import type { HoldingRow } from "@/lib/dashboard";
import { entityName, entitySub, GRADING_OPTIONS } from "./common";

const BINDERS = [
  { value: "premium", label: "GOD binder (premium)" },
  { value: "regular", label: "Collection (regular)" },
  { value: "graded", label: "Graded slabs" },
  { value: "sealed", label: "Sealed" },
];
const CONDITIONS = ["Mint", "Near Mint", "Slightly Played", "Moderately Played", "Played", "Poor"];

function L({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block text-xs text-ink-3">{label}</span>
      {children}
    </label>
  );
}

interface FormState {
  quantity: string;
  acquisition_price_nok: string;
  acquisition_date: string;
  binder_type: string;
  condition: string;
  grading_status: string;
  grade_company: string;
  psa_grade: string;
  notes: string;
}

function Fields({ f, set, isProduct }: { f: FormState; set: (k: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => void; isProduct: boolean }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <L label="Quantity">
        <input className={input} type="number" min="1" inputMode="numeric" value={f.quantity} onChange={set("quantity")} required />
      </L>
      <L label="Price paid per unit (NOK)">
        <input className={input} type="number" min="0" step="any" inputMode="decimal" value={f.acquisition_price_nok} onChange={set("acquisition_price_nok")} required />
      </L>
      <L label="Purchase date">
        <input className={input} type="date" value={f.acquisition_date} onChange={set("acquisition_date")} />
      </L>
      <L label="Binder">
        <select className={input} value={f.binder_type} onChange={set("binder_type")}>
          {BINDERS.map((b) => <option key={b.value} value={b.value}>{b.label}</option>)}
        </select>
      </L>
      {!isProduct && (
        <>
          <L label="Condition">
            <select className={input} value={f.condition} onChange={set("condition")}>
              {CONDITIONS.map((c) => <option key={c}>{c}</option>)}
            </select>
          </L>
          <L label="Grading status">
            <select className={input} value={f.grading_status} onChange={set("grading_status")}>
              {GRADING_OPTIONS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
            </select>
          </L>
          <L label="Grader">
            <input className={input} value={f.grade_company} onChange={set("grade_company")} disabled={f.grading_status !== "graded"} />
          </L>
          <L label="Grade">
            <input className={input} type="number" min="1" max="10" step="0.5" value={f.psa_grade} onChange={set("psa_grade")} disabled={f.grading_status !== "graded"} />
          </L>
        </>
      )}
      <L label="Notes" className="col-span-2 md:col-span-4">
        <input className={input} value={f.notes} onChange={set("notes")} placeholder="Centering, where you bought it…" />
      </L>
    </div>
  );
}

function payload(f: FormState, isProduct: boolean) {
  const graded = !isProduct && f.grading_status === "graded";
  return {
    quantity: Number(f.quantity) || 1,
    acquisition_price_nok: Number(f.acquisition_price_nok) || 0,
    acquisition_date: f.acquisition_date || null,
    binder_type: isProduct ? "sealed" : f.binder_type,
    condition: isProduct ? null : f.condition,
    grading_status: isProduct ? "raw" : f.grading_status,
    grade_company: graded ? f.grade_company || "PSA" : null,
    psa_grade: graded && f.psa_grade ? Number(f.psa_grade) : null,
    notes: f.notes || null,
  };
}

const EMPTY: FormState = {
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

export function AddHoldingForm({ onDone, onCancel }: { onDone: () => void; onCancel?: () => void }) {
  const [pick, setPick] = useState<EntityPick | null>(null);
  const [f, setF] = useState<FormState>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  const isProduct = pick?.entity_type === "product";

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!pick) return;
    setBusy(true);
    setError(null);
    try {
      await api("portfolio", {
        method: "POST",
        json: { card_id: isProduct ? null : pick.entity_id, product_id: isProduct ? pick.entity_id : null, ...payload(f, isProduct) },
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
    <form onSubmit={submit} className="space-y-4">
      <ErrorBox error={error} />
      <L label="Card or sealed product">
        {pick ? (
          <div className="flex items-center justify-between gap-2 rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm">
            <span className="truncate text-ink">{pick.label}</span>
            <button type="button" className="text-xs text-ink-3 hover:text-ink" onClick={() => setPick(null)}>change</button>
          </div>
        ) : (
          <EntitySearch onPick={(p) => { setPick(p); if (p.entity_type === "product") setF((x) => ({ ...x, binder_type: "sealed" })); }} placeholder="Search e.g. “Gastly 177” or “Paradox Rift booster box”" />
        )}
      </L>
      <Fields f={f} set={set} isProduct={isProduct} />
      <div className="flex justify-end gap-2">
        {onCancel && <button type="button" className={btn} onClick={onCancel}>Cancel</button>}
        <button className={btnPrimary} disabled={!pick || busy || !f.acquisition_price_nok}>{busy ? "Adding…" : "Add to portfolio"}</button>
      </div>
    </form>
  );
}

/** Slide-over editor for one holding (PATCH / DELETE /portfolio/{id}). */
export function EditHoldingDrawer({ h, onClose, onSaved }: { h: HoldingRow; onClose: () => void; onSaved: () => void }) {
  const isProduct = h.entity?.type === "product";
  const [f, setF] = useState<FormState>({
    quantity: String(h.quantity),
    acquisition_price_nok: String(h.acquisition_price_nok),
    acquisition_date: h.acquisition_date ?? "",
    binder_type: h.binder_type,
    condition: h.condition ?? "Near Mint",
    grading_status: h.grading_status,
    grade_company: h.grade_company ?? "PSA",
    psa_grade: h.grade ? String(h.grade) : "",
    notes: h.notes ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onSaved();
      onClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50">
      <button className="absolute inset-0 bg-black/60" aria-label="Close" onClick={onClose} />
      <div className="absolute inset-y-0 right-0 flex w-full max-w-lg flex-col border-l border-line bg-surface">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <CardThumb src={h.entity?.image_url} alt={h.entity?.name ?? ""} size="sm" />
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-ink">{entityName(h.entity)}</div>
              <div className="truncate text-xs text-ink-3">{entitySub(h.entity)}</div>
            </div>
          </div>
          <button className="rounded-lg p-2 text-ink-3 hover:bg-surface-2 hover:text-ink" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>
        <form
          className="flex-1 space-y-4 overflow-y-auto p-4"
          onSubmit={(e) => {
            e.preventDefault();
            run(() => api(`portfolio/${h.id}`, { method: "PATCH", json: payload(f, isProduct) }));
          }}
        >
          <ErrorBox error={error} />
          <Fields f={f} set={set} isProduct={isProduct} />
          <div className="flex items-center justify-between gap-2 border-t border-line pt-4">
            <button type="button" className={btnDanger} disabled={busy}
              onClick={() => confirm(`Remove ${entityName(h.entity)} from the portfolio?`) && run(() => api(`portfolio/${h.id}`, { method: "DELETE" }))}>
              <Trash2 size={13} /> Remove
            </button>
            <div className="flex gap-2">
              <button type="button" className={btn} onClick={onClose}>Cancel</button>
              <button className={btnPrimary} disabled={busy}>{busy ? "Saving…" : "Save"}</button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

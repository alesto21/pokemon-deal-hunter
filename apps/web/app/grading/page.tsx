"use client";

import { Award, CircleAlert, Plus, RefreshCw, X } from "lucide-react";
import Link from "next/link";
import { type FormEvent, useState } from "react";
import { entityName, GRADING_OPTIONS } from "@/components/portfolio/common";
import {
  Badge,
  btn,
  btnGhost,
  btnPrimary,
  CardThumb,
  type Column,
  DataTable,
  EmptyState,
  ErrorBox,
  input,
  KpiCard,
  Loading,
  PageHeader,
  Panel,
} from "@/components/ui";
import { api, useApi } from "@/lib/api";
import type { GradedRef, Grading, GradingRow } from "@/lib/dashboard";
import { day, gainClass, nok, pct } from "@/lib/format";

/* ------------------------------------------------------------------ add PSA reference */
function AddRefDialog({ row, grade, onClose, onSaved }: { row: GradingRow; grade: 9 | 10; onClose: () => void; onSaved: () => void }) {
  const [g, setG] = useState<number>(grade);
  const [price, setPrice] = useState("");
  const [source, setSource] = useState("manual");
  const [confidence, setConfidence] = useState("0.7");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!row.entity) return;
    setBusy(true);
    setError(null);
    try {
      await api("graded", {
        method: "POST",
        json: { card_id: row.entity.id, grade_company: "PSA", grade: g, price_nok: Number(price), source: source || "manual", confidence: Number(confidence) },
      });
      onSaved();
      onClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4">
      <button className="absolute inset-0 bg-black/60" aria-label="Close" onClick={onClose} />
      <form onSubmit={submit} className="relative w-full max-w-sm space-y-3 rounded-xl border border-line bg-surface p-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-ink">Add PSA reference</div>
            <div className="text-xs text-ink-3">{entityName(row.entity)}</div>
          </div>
          <button type="button" className="rounded-lg p-1.5 text-ink-3 hover:bg-surface-2" onClick={onClose} aria-label="Close"><X size={16} /></button>
        </div>
        <ErrorBox error={error} />
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="mb-1 block text-xs text-ink-3">Grade</span>
            <select className={input} value={g} onChange={(e) => setG(Number(e.target.value))}>
              <option value={10}>PSA 10</option>
              <option value={9}>PSA 9</option>
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-ink-3">Price (NOK)</span>
            <input className={input} type="number" min="1" step="any" inputMode="decimal" required value={price} onChange={(e) => setPrice(e.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-ink-3">Source</span>
            <input className={input} value={source} onChange={(e) => setSource(e.target.value)} placeholder="e.g. eBay sold, 130point" />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-ink-3">Confidence (0–1)</span>
            <input className={input} type="number" min="0" max="1" step="0.05" value={confidence} onChange={(e) => setConfidence(e.target.value)} />
          </label>
        </div>
        <p className="text-xs text-ink-3">Use a real recent sold price. The dashboard never estimates PSA values.</p>
        <div className="flex justify-end gap-2">
          <button type="button" className={btn} onClick={onClose}>Cancel</button>
          <button className={btnPrimary} disabled={busy || !price}>{busy ? "Saving…" : "Save reference"}</button>
        </div>
      </form>
    </div>
  );
}

/* ------------------------------------------------------------------ cells */
function RefCell({ refVal, onAdd }: { refVal: GradedRef | null; onAdd: () => void }) {
  if (!refVal) {
    return (
      <button onClick={onAdd} title="Add a PSA reference (real sold price)" className="inline-flex items-center gap-1 whitespace-nowrap rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[11px] font-medium text-amber-300 ring-1 ring-inset ring-amber-400/30 hover:bg-amber-500/20">
        <CircleAlert size={11} /> Missing +
      </button>
    );
  }
  return (
    <div className="whitespace-nowrap" title={`${refVal.source} · updated ${day(refVal.updated_at)} · confidence ${pct(refVal.confidence, 0)}`}>
      <div className="num text-ink">{nok(refVal.price_nok)}</div>
      <div className="max-w-32 truncate text-[11px] text-ink-3">{refVal.source}</div>
    </div>
  );
}

function NetCell({ net, upside }: { net: number | null; upside: number | null }) {
  if (net === null) return <span className="whitespace-nowrap text-xs text-ink-3">needs data</span>;
  return (
    <div className={`whitespace-nowrap ${gainClass(net)}`}>
      <div className="num">{`${net > 0 ? "+" : ""}${nok(net)}`}</div>
      {upside !== null && <div className="num text-[11px] opacity-80">{pct(upside, 0, true)} of raw</div>}
    </div>
  );
}

const VERDICT_TONE: Record<string, "gain" | "warn" | "neutral" | "loss"> = { Strong: "gain", Moderate: "warn", Weak: "neutral", None: "loss", Unknown: "neutral" };

function Verdict({ r }: { r: GradingRow }) {
  return (
    <div className="space-y-1">
      <Badge tone={VERDICT_TONE[r.grading_label] ?? "neutral"}>{r.grading_label === "Unknown" ? "Needs PSA data" : `${r.grading_label} upside`}</Badge>
      {r.flags.length > 0 && (
        <div className="text-[11px] leading-tight text-amber-200/80" title={r.flags.join("\n")}>
          {r.flags[0]}
          {r.flags.length > 1 && <span className="text-ink-3"> +{r.flags.length - 1} more</span>}
        </div>
      )}
    </div>
  );
}

function StatusSelect({ r, onChange }: { r: GradingRow; onChange: (id: number, status: string) => void }) {
  return (
    <select className={`${input} w-auto! py-1 text-xs`} value={r.grading_status} onChange={(e) => onChange(r.id, e.target.value)} aria-label="Grading status" onClick={(e) => e.stopPropagation()}>
      {GRADING_OPTIONS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
    </select>
  );
}

function CardCell({ r }: { r: GradingRow }) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <CardThumb src={r.entity?.image_url} alt={r.entity?.name ?? ""} size="sm" />
      <div className="min-w-0">
        <div className="truncate text-ink">{entityName(r.entity)}</div>
        <div className="truncate text-xs text-ink-3">{r.entity?.set_name}</div>
        {r.notes && <div className="truncate text-[11px] italic text-ink-3" title={r.notes}>{r.notes}</div>}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ page */
export default function GradingPage() {
  const { data, error, loading, reload } = useApi<Grading>("dashboard/grading");
  const [adding, setAdding] = useState<{ row: GradingRow; grade: 9 | 10 } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function setStatus(id: number, status: string) {
    setActionError(null);
    try {
      await api(`portfolio/${id}`, { method: "PATCH", json: { grading_status: status } });
      reload();
    } catch (err) {
      setActionError((err as Error).message);
    }
  }

  const candidateCols: Column<GradingRow>[] = [
    { key: "card", header: "Card", cell: (r) => <CardCell r={r} /> },
    {
      key: "raw",
      header: "Raw value",
      align: "right",
      cell: (r) => (
        <div className="whitespace-nowrap">
          <div>{r.raw_value_nok !== null ? nok(r.raw_value_nok) : <span className="text-amber-300">no price</span>}</div>
          <div className="text-[11px] text-ink-3">paid {nok(r.acquisition_price_nok)}</div>
        </div>
      ),
    },
    { key: "psa9", header: "PSA 9", align: "right", cell: (r) => <RefCell refVal={r.psa9} onAdd={() => setAdding({ row: r, grade: 9 })} /> },
    { key: "psa10", header: "PSA 10", align: "right", cell: (r) => <RefCell refVal={r.psa10} onAdd={() => setAdding({ row: r, grade: 10 })} /> },
    { key: "net9", header: "Net PSA 9", align: "right", hideBelow: "lg", cell: (r) => <NetCell net={r.psa9_net_nok} upside={r.upside_psa9} /> },
    { key: "net10", header: "Net PSA 10", align: "right", cell: (r) => <NetCell net={r.psa10_net_nok} upside={r.upside_psa10} /> },
    { key: "verdict", header: "Economics", hideBelow: "xl", className: "max-w-56", cell: (r) => <Verdict r={r} /> },
    { key: "status", header: "Status", cell: (r) => <StatusSelect r={r} onChange={setStatus} /> },
  ];

  const candidateCard = (r: GradingRow) => (
    <div className="space-y-2">
      <CardCell r={r} />
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <div><div className="text-ink-3">Raw value</div><div className="num text-ink">{nok(r.raw_value_nok)}</div></div>
        <div><div className="text-ink-3">Paid</div><div className="num text-ink">{nok(r.acquisition_price_nok)}</div></div>
        <div><div className="text-ink-3">PSA 9</div><RefCell refVal={r.psa9} onAdd={() => setAdding({ row: r, grade: 9 })} /></div>
        <div><div className="text-ink-3">PSA 10</div><RefCell refVal={r.psa10} onAdd={() => setAdding({ row: r, grade: 10 })} /></div>
        <div><div className="text-ink-3">Net at PSA 9</div><NetCell net={r.psa9_net_nok} upside={r.upside_psa9} /></div>
        <div><div className="text-ink-3">Net at PSA 10</div><NetCell net={r.psa10_net_nok} upside={r.upside_psa10} /></div>
      </div>
      <div className="flex items-start justify-between gap-2">
        <Verdict r={r} />
        <StatusSelect r={r} onChange={setStatus} />
      </div>
    </div>
  );

  const pipelineCols: Column<GradingRow>[] = [
    { key: "card", header: "Card", cell: (r) => <CardCell r={r} /> },
    { key: "raw", header: "Raw value", align: "right", cell: (r) => nok(r.raw_value_nok) },
    { key: "psa10", header: "PSA 10 ref", align: "right", hideBelow: "md", cell: (r) => (r.psa10 ? nok(r.psa10.price_nok) : <span className="text-ink-3">—</span>) },
    { key: "grade", header: "Grade", align: "right", cell: (r) => (r.grade ? `${r.grade_company ?? "PSA"} ${r.grade}` : <span className="text-ink-3">—</span>) },
    { key: "status", header: "Status", cell: (r) => <StatusSelect r={r} onChange={setStatus} /> },
  ];
  const pipelineCard = (r: GradingRow) => (
    <div className="space-y-2">
      <CardCell r={r} />
      <div className="flex items-center justify-between gap-2 text-xs text-ink-3">
        <span>{r.grade ? `${r.grade_company ?? "PSA"} ${r.grade}` : `Raw value ${nok(r.raw_value_nok)}`}</span>
        <StatusSelect r={r} onChange={setStatus} />
      </div>
    </div>
  );

  const c = data?.counts;
  const total = c ? c.candidates + c.submitted + c.at_grader + c.returned : 0;
  const missingData = data ? data.candidates.filter((r) => r.missing.length > 0).length : 0;

  return (
    <>
      <PageHeader
        title="Grading"
        icon={Award}
        subtitle={data ? `Grading economics use your PSA references and an estimated ${nok(data.grading_cost_nok)} per card` : "Grading economics from your own PSA references"}
        actions={
          <button className={btnGhost} onClick={reload} disabled={loading}>
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        }
      />
      <ErrorBox error={error ?? actionError} />
      <Loading show={loading && !data} />
      {data && c && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <KpiCard label="Candidates" value={c.candidates} hint={missingData ? `${missingData} missing PSA data` : "raw cards you own"} />
            <KpiCard label="Submitted" value={c.submitted} hint="sent, not yet received" />
            <KpiCard label="At grader" value={c.at_grader} hint="in grading" />
            <KpiCard label="Returned" value={c.returned} hint="graded & back" />
          </div>

          {total === 0 ? (
            <Panel>
              <EmptyState icon={Award} title="No cards to grade yet"
                action={<Link href="/portfolio?add=1" className={btnPrimary}><Plus size={15} /> Add a card</Link>}>
                Raw cards in your portfolio appear here as grading candidates. Add PSA 9/10 sold prices to see whether
                grading pays after the grading cost — PSA values are never estimated.
              </EmptyState>
            </Panel>
          ) : (
            <>
              <Panel title={`Grading candidates · ${c.candidates}`} subtitle="Raw cards you own, best PSA 10 economics first. Net = PSA price − raw value − grading cost.">
                <DataTable rows={data.candidates} columns={candidateCols} rowKey={(r) => r.id} mobileCard={candidateCard}
                  empty={<EmptyState title="No raw cards — everything is submitted or graded" />} />
              </Panel>
              {(["submitted", "at_grader", "returned"] as const).map((k) => (
                <Panel key={k} title={`${k === "at_grader" ? "At grader" : k[0].toUpperCase() + k.slice(1)} · ${c[k]}`}>
                  <DataTable rows={data[k]} columns={pipelineCols} rowKey={(r) => r.id} mobileCard={pipelineCard}
                    empty={<div className="py-3 text-center text-sm text-ink-3">Nothing {k === "returned" ? "returned" : k.replace("_", " ")} right now.</div>} />
                </Panel>
              ))}
            </>
          )}
        </div>
      )}
      {adding && <AddRefDialog row={adding.row} grade={adding.grade} onClose={() => setAdding(null)} onSaved={reload} />}
    </>
  );
}

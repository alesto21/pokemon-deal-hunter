"use client";

import { CheckCircle2, ExternalLink, XCircle } from "lucide-react";
import { useState } from "react";
import { sourceLabel } from "@/components/deals/bits";
import EntitySearch from "@/components/EntitySearch";
import { Badge, CardThumb, EmptyState, ErrorBox, Loading, btn, btnDanger, btnPrimary } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { nok, num, rel } from "@/lib/format";
import type { Listing } from "@/lib/types";

/** Match review: confidence 0.70–0.89 needs review; below 0.70 unresolved. Nothing low-confidence auto-matches. */
export default function ReviewQueue({ onChanged }: { onChanged?: () => void }) {
  const [includeUnresolved, setIncludeUnresolved] = useState(true);
  const { data, error, loading, reload } = useApi<Listing[]>(`review?include_unresolved=${includeUnresolved}`);
  const [actionError, setActionError] = useState<string | null>(null);

  async function decide(id: number, body: Record<string, unknown>) {
    setActionError(null);
    try {
      await api(`review/${id}`, { method: "POST", json: body });
      reload();
      onChanged?.();
    } catch (e) {
      setActionError((e as Error).message);
    }
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-ink-3">Matches with confidence 0.70–0.89 need review; below 0.70 they are unresolved. Nothing low-confidence is auto-matched.</p>
        <label className="flex items-center gap-2 text-sm text-ink-2">
          <input type="checkbox" className="accent-[var(--color-gold)]" checked={includeUnresolved} onChange={(e) => setIncludeUnresolved(e.target.checked)} />
          include unresolved
        </label>
      </div>
      <ErrorBox error={error ?? actionError} />
      <Loading show={loading && !data} />
      {data && data.length === 0 && (
        <EmptyState icon={CheckCircle2} title="Review queue is empty">
          Every active listing is either confidently matched or rejected.
        </EmptyState>
      )}
      <div className="space-y-3">
        {data?.map((l) => (
          <article key={l.id} className="rounded-xl border border-line bg-surface p-4">
            <div className="flex gap-3">
              <CardThumb src={l.image_urls[0]} alt={l.title} size="sm" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="break-words font-medium text-ink">{l.title}</div>
                    <div className="text-xs text-ink-3">
                      {sourceLabel(l.source)} · {l.listing_kind} · first seen {rel(l.first_seen)}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone={l.match_status === "review" ? "warn" : "neutral"}>
                      {l.match_status} · {num(l.confidence, 2)}
                    </Badge>
                    <span className="num text-sm text-ink">{nok(l.landed_cost_nok)}</span>
                  </div>
                </div>
                {l.entity_label && (
                  <div className="mt-1 text-sm text-ink-2">
                    Current best guess: <b className="text-ink">{l.entity_label}</b>
                  </div>
                )}
                {l.url && (
                  <a className="mt-1 inline-flex items-center gap-1 text-xs text-ink-2 hover:text-gold" href={l.url} target="_blank" rel="noopener noreferrer">
                    Open listing <ExternalLink size={12} />
                  </a>
                )}
              </div>
            </div>
            {l.match_candidates.length > 0 ? (
              <ul className="mt-3 space-y-1.5">
                {l.match_candidates.map((c, i) => (
                  <li key={`${c.entity_type}-${c.entity_id}`} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm">
                    <div className="min-w-0">
                      <span className="mr-2 text-[10px] uppercase tracking-wider text-ink-3">{c.entity_type}</span>
                      <span className="text-ink">{c.label}</span>
                      <span className="num ml-2 text-ink-3">{num(c.score, 2)}</span>
                      <div className="text-xs text-ink-3">{c.reasons.join(" · ")}</div>
                    </div>
                    <button className={i === 0 ? btnPrimary : btn} onClick={() => decide(l.id, { action: "set", entity_type: c.entity_type, entity_id: c.entity_id })}>
                      Use this
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="mt-3 text-sm text-ink-3">No candidates found.</div>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <div className="min-w-0 flex-1 basis-64">
                <EntitySearch placeholder="Assign manually: search card or product…" onPick={(p) => decide(l.id, { action: "set", entity_type: p.entity_type, entity_id: p.entity_id })} />
              </div>
              <button className={btnDanger} onClick={() => decide(l.id, { action: "reject" })}>
                <XCircle size={12} /> Reject (no match)
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

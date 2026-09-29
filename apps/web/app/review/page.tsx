"use client";

import { useState } from "react";
import EntitySearch from "@/components/EntitySearch";
import { Empty, ErrorBox, Loading, PageHeader, Panel, btn, btnDanger, btnPrimary } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { nok, num } from "@/lib/format";
import type { Listing } from "@/lib/types";

export default function ReviewPage() {
  const [includeUnresolved, setIncludeUnresolved] = useState(true);
  const { data, error, loading, reload } = useApi<Listing[]>(`review?include_unresolved=${includeUnresolved}`);
  const [actionError, setActionError] = useState<string | null>(null);

  async function decide(id: number, body: Record<string, unknown>) {
    setActionError(null);
    try {
      await api(`review/${id}`, { method: "POST", json: body });
      reload();
    } catch (e) {
      setActionError((e as Error).message);
    }
  }

  return (
    <>
      <PageHeader
        title="Match review"
        subtitle="Matches with confidence 0.70–0.89 need review; below 0.70 they're unresolved. Nothing low-confidence is auto-matched."
        actions={
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={includeUnresolved} onChange={(e) => setIncludeUnresolved(e.target.checked)} />
            include unresolved
          </label>
        }
      />
      <ErrorBox error={error ?? actionError} />
      <Loading show={loading && !data} />
      {data && data.length === 0 && <Empty>Review queue is empty 🎉</Empty>}
      <div className="space-y-4">
        {data?.map((l) => (
          <Panel
            key={l.id}
            title={l.title}
            actions={<span className="text-xs text-zinc-500">{l.source} · {l.match_status} · conf {num(l.confidence, 2)}</span>}
          >
            <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
              <span className="tabular-nums">{nok(l.total_price_nok)}</span>
              <span className="text-zinc-500">{l.listing_kind}</span>
              {l.entity_label && <span>current match: <b>{l.entity_label}</b></span>}
              {l.url && <a className={btn} href={l.url} target="_blank" rel="noopener noreferrer">Open ↗</a>}
            </div>
            {l.match_candidates.length > 0 ? (
              <ul className="mb-3 space-y-1.5">
                {l.match_candidates.map((c, i) => (
                  <li key={`${c.entity_type}-${c.entity_id}`} className="flex flex-wrap items-center justify-between gap-2 rounded border border-zinc-200 px-3 py-1.5 text-sm dark:border-zinc-800">
                    <div>
                      <span className="mr-2 text-xs uppercase text-zinc-400">{c.entity_type}</span>
                      {c.label} <span className="ml-2 tabular-nums text-zinc-500">{num(c.score, 2)}</span>
                      <div className="text-xs text-zinc-500">{c.reasons.join(" · ")}</div>
                    </div>
                    <button
                      className={i === 0 ? btnPrimary : btn}
                      onClick={() => decide(l.id, { action: "set", entity_type: c.entity_type, entity_id: c.entity_id })}
                    >
                      Use this
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="mb-3 text-sm text-zinc-500">No candidates found.</div>
            )}
            <div className="flex flex-wrap items-center gap-2">
              <div className="min-w-64 flex-1">
                <EntitySearch
                  placeholder="Assign manually: search card or product…"
                  onPick={(p) => decide(l.id, { action: "set", entity_type: p.entity_type, entity_id: p.entity_id })}
                />
              </div>
              <button className={btnDanger} onClick={() => decide(l.id, { action: "reject" })}>Reject (no match)</button>
            </div>
          </Panel>
        ))}
      </div>
    </>
  );
}

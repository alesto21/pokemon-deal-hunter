"use client";

import { ArrowLeft, ExternalLink, Layers, Trash2 } from "lucide-react";
import Link from "next/link";
import { use, useState, type FormEvent } from "react";
import { sourceLabel } from "@/components/deals/bits";
import EntitySearch, { type EntityPick } from "@/components/EntitySearch";
import { Badge, Empty, EmptyState, ErrorBox, KpiCard, LevelBadge, Loading, PageHeader, Panel, btn, btnDanger, btnGhost, btnPrimary, input, td, th } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { nok, num, pct } from "@/lib/format";
import type { ListingDetail, Lot } from "@/lib/types";

export default function LotPage({ params }: { params: Promise<{ listingId: string }> }) {
  const { listingId } = use(params);
  const valid = /^\d+$/.test(listingId);
  const listing = useApi<ListingDetail>(valid ? `listings/${listingId}` : null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pick, setPick] = useState<EntityPick | null>(null);
  const [item, setItem] = useState({ label: "", manual_value_nok: "", quantity: "1", condition: "" });
  const [file, setFile] = useState<File | null>(null);

  const l = listing.data;
  const lot = l?.lot;

  async function run(fn: () => Promise<unknown>) {
    setActionError(null);
    try {
      await fn();
      listing.reload();
    } catch (e) {
      setActionError((e as Error).message);
    }
  }

  function addItem(e: FormEvent) {
    e.preventDefault();
    if (!lot) return;
    run(async () => {
      await api<Lot>(`lots/${lot.id}/items`, {
        method: "POST",
        json: {
          card_id: pick?.entity_type === "card" ? pick.entity_id : null,
          product_id: pick?.entity_type === "product" ? pick.entity_id : null,
          label: item.label || pick?.label || null,
          manual_value_nok: item.manual_value_nok ? Number(item.manual_value_nok) : null,
          quantity: Number(item.quantity) || 1,
          condition: item.condition || null,
        },
      });
      setPick(null);
      setItem({ label: "", manual_value_nok: "", quantity: "1", condition: "" });
    });
  }

  function upload(e: FormEvent) {
    e.preventDefault();
    if (!lot || !file) return;
    const fd = new FormData();
    fd.append("file", file);
    run(async () => {
      await api(`lots/${lot.id}/images`, { method: "POST", body: fd });
      setFile(null);
    });
  }

  if (!valid) return <ErrorBox error="Invalid listing id" />;

  return (
    <>
      <PageHeader
        title="Lot breakdown"
        icon={Layers}
        subtitle="Mark the cards in a lot manually to get an estimated and a conservative lot value. Image recognition is planned for phase 2."
        actions={
          valid ? (
            <Link className={btnGhost} href={`/deals?listing=${listingId}`}>
              <ArrowLeft size={14} /> Deal detail
            </Link>
          ) : undefined
        }
      />
      <ErrorBox error={listing.error ?? actionError} />
      <Loading show={listing.loading && !l} />
      {l && (
        <div className="space-y-6">
          <Panel
            title={l.title}
            actions={
              l.url ? (
                <a className={btn} href={l.url} target="_blank" rel="noopener noreferrer">
                  Open listing <ExternalLink size={14} />
                </a>
              ) : undefined
            }
          >
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-ink-2">
              <span>
                Landed cost <b className="num text-ink">{nok(l.landed_cost_nok)}</b>
              </span>
              <span>Source {sourceLabel(l.source)}</span>
              <Badge>{l.listing_kind}</Badge>
              {l.evaluation && (
                <span className="flex items-center gap-2">
                  Score <b className="num text-ink">{num(l.evaluation.total_score, 1)}</b> <LevelBadge level={l.evaluation.alert_level} /> discount {pct(l.evaluation.discount_pct)}
                </span>
              )}
            </div>
          </Panel>

          {!lot ? (
            <Panel>
              <EmptyState
                icon={Layers}
                title="No lot breakdown yet"
                action={
                  <button className={btnPrimary} onClick={() => run(() => api("lots", { method: "POST", json: { listing_id: l.id } }))}>
                    Create lot
                  </button>
                }
              >
                Creating one marks this listing as a lot and values it from the items you add.
              </EmptyState>
            </Panel>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <KpiCard label="Estimated value" value={nok(lot.valuation.estimated_value_nok)} />
                <KpiCard label="Conservative value" value={nok(lot.valuation.conservative_value_nok)} tone="gold" hint="low fair values × liquidity haircut" />
                <KpiCard label="Priced items" value={`${lot.valuation.priced_items} / ${lot.valuation.total_items}`} />
                <KpiCard
                  label="Price vs conservative"
                  value={lot.valuation.conservative_value_nok ? pct((lot.valuation.conservative_value_nok - l.landed_cost_nok) / lot.valuation.conservative_value_nok) : "—"}
                  hint="positive = below value"
                />
              </div>
              <div className="grid gap-6 lg:grid-cols-2">
                <Panel title="Items">
                  {lot.valuation.lines.length === 0 ? (
                    <Empty>No items yet.</Empty>
                  ) : (
                    <table className="w-full">
                      <thead className="border-b border-line">
                        <tr>
                          <th className={th}>Item</th>
                          <th className={`${th} text-right`}>Qty</th>
                          <th className={`${th} text-right`}>Unit value</th>
                          <th className={th}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {lot.valuation.lines.map((line) => (
                          <tr key={line.id} className="border-b border-line/60">
                            <td className={td}>{line.label ?? (line.card_id ? `card #${line.card_id}` : `product #${line.product_id}`)}</td>
                            <td className={`${td} text-right num`}>{line.quantity}</td>
                            <td className={`${td} text-right num`}>{nok(line.unit_value_nok)}</td>
                            <td className={`${td} text-right`}>
                              <button className={btnDanger} aria-label="Remove item" onClick={() => run(() => api(`lots/${lot.id}/items/${line.id}`, { method: "DELETE" }))}>
                                <Trash2 size={12} />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  <form onSubmit={addItem} className="mt-4 space-y-2 border-t border-line pt-4">
                    <div className="text-sm font-medium text-ink">Add item</div>
                    {pick ? (
                      <div className="flex items-center justify-between rounded-lg border border-line bg-surface-2 px-2.5 py-1.5 text-sm">
                        <span>{pick.label}</span>
                        <button type="button" className="text-xs text-ink-3 hover:text-ink" onClick={() => setPick(null)}>
                          change
                        </button>
                      </div>
                    ) : (
                      <EntitySearch onPick={setPick} placeholder="Catalogue card/product (optional)…" />
                    )}
                    <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                      <input className={input} placeholder="Free label" value={item.label} onChange={(e) => setItem({ ...item, label: e.target.value })} />
                      <input className={input} type="number" min="0" step="any" placeholder="Manual value NOK" value={item.manual_value_nok} onChange={(e) => setItem({ ...item, manual_value_nok: e.target.value })} />
                      <input className={input} type="number" min="1" placeholder="Qty" value={item.quantity} onChange={(e) => setItem({ ...item, quantity: e.target.value })} />
                      <input className={input} placeholder="Condition" value={item.condition} onChange={(e) => setItem({ ...item, condition: e.target.value })} />
                    </div>
                    <button className={btnPrimary} disabled={!pick && !(item.label && item.manual_value_nok)}>Add item</button>
                  </form>
                </Panel>
                <Panel title="Images">
                  {lot.images.length === 0 ? (
                    <Empty>No images uploaded.</Empty>
                  ) : (
                    <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
                      {lot.images.map((name) => (
                        <a key={name} href={`/api/proxy/lots/${lot.id}/images/${name}`} target="_blank" rel="noopener noreferrer">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img src={`/api/proxy/lots/${lot.id}/images/${name}`} alt="lot" className="aspect-square w-full rounded-lg border border-line object-cover" />
                        </a>
                      ))}
                    </div>
                  )}
                  <form onSubmit={upload} className="mt-4 flex flex-wrap items-center gap-2">
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      className="min-w-0 flex-1 text-sm text-ink-2 file:mr-3 file:rounded-lg file:border file:border-line file:bg-surface-3 file:px-3 file:py-1.5 file:text-ink"
                      onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                    <button className={btn} disabled={!file}>Upload</button>
                  </form>
                  <p className="mt-2 text-xs text-ink-3">JPEG/PNG/WebP, max 10 MB. Stored on the server&apos;s data volume.</p>
                </Panel>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}

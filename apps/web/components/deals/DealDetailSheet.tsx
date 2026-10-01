"use client";

import { Ban, BellRing, CircleCheck, ExternalLink, Info, Layers, ShieldAlert, X } from "lucide-react";
import Link from "next/link";
import { type ReactNode, useEffect } from "react";
import { Badge, CardThumb, ErrorBox, Field, LevelBadge, Loading, ProgressBar, btn } from "@/components/ui";
import { useApi } from "@/lib/api";
import type { DealDetail } from "@/lib/dashboard";
import { dt, gainClass, nok, num, pct, rel } from "@/lib/format";
import { entitySub, entityTitle, sourceLabel } from "./bits";

const COMPONENT_LABEL: Record<string, string> = {
  discount_to_fair_value: "Discount vs fair value",
  liquidity: "Liquidity",
  pokemon_popularity: "Pokémon popularity",
  set_desirability: "Set desirability",
  trend: "Trend",
  grading_upside: "Grading upside",
  scarcity: "Scarcity",
};

function Block({ title, icon, children, tone }: { title: string; icon: ReactNode; children: ReactNode; tone?: string }) {
  return (
    <section className={`rounded-xl border border-line bg-surface-2/60 p-4 ${tone ?? ""}`}>
      <h3 className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-ink-3">
        {icon}
        {title}
      </h3>
      {children}
    </section>
  );
}

function Notes({ items, tone }: { items: string[]; tone: "warn" | "gain" | "info" }) {
  if (!items.length) return null;
  const cls = tone === "warn" ? "text-amber-300" : tone === "gain" ? "text-emerald-300" : "text-ink-2";
  return (
    <ul className={`mt-2 space-y-1 text-sm ${cls}`}>
      {items.map((t) => (
        <li key={t} className="flex gap-2">
          <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-current" />
          <span>{t}</span>
        </li>
      ))}
    </ul>
  );
}

function DetailBody({ d }: { d: DealDetail }) {
  const m = d.market;
  const capped = d.raw_band !== d.level;
  const n = d.notification;
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex gap-4">
        <CardThumb src={d.entity?.image_url} alt={entityTitle(d.entity, d.title)} size="lg" className="hidden sm:block" />
        <CardThumb src={d.entity?.image_url} alt={entityTitle(d.entity, d.title)} size="md" className="sm:hidden" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <LevelBadge level={d.level} size="md" />
            {capped && <Badge tone="warn" title="Score band before caps">band {d.raw_band.replace("_", " ").toLowerCase()}</Badge>}
            <span className="num text-sm text-ink-3">score {num(d.score, 1)}</span>
          </div>
          <h2 className="mt-2 text-lg font-semibold leading-tight text-ink">{entityTitle(d.entity, d.title)}</h2>
          <div className="text-sm text-ink-3">{entitySub(d.entity)}</div>
          <div className="mt-1 truncate text-xs text-ink-3" title={d.title}>
            Listing: {d.title}
          </div>
          <div className="mt-3 flex flex-wrap items-baseline gap-x-5 gap-y-1">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-ink-3">Landed</div>
              <div className="num text-xl font-semibold text-ink">{nok(d.price.landed_nok)}</div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wider text-ink-3">Fair value</div>
              <div className="num text-xl font-semibold text-gold">{nok(d.fair_value_nok)}</div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wider text-ink-3">Discount</div>
              <div className={`num text-xl font-semibold ${gainClass(d.discount_pct)}`}>
                {pct(d.discount_pct)} <span className="text-sm font-normal">({nok(d.discount_nok)})</span>
              </div>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {d.url && (
              <a className={btn} href={d.url} target="_blank" rel="noopener noreferrer">
                Open listing <ExternalLink size={14} />
              </a>
            )}
            <Link className={btn} href={`/lots/${d.listing_id}`}>
              <Layers size={14} /> Lot breakdown
            </Link>
            {d.entity?.type === "card" && (
              <Link className={btn} href={`/market?type=card&id=${d.entity.id}`}>
                Price history
              </Link>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* PRICE */}
        <Block title="Price" icon={<span className="text-gold">1</span>}>
          <Field label={`Item (${num(d.price.asking, 2)} ${d.price.currency})`} value={nok(d.price.item_nok)} />
          <Field label="Shipping (est.)" value={nok(d.price.shipping_nok)} />
          <Field label="Import buffer (est.)" value={nok(d.price.import_buffer_nok)} />
          <div className="my-1 border-t border-line" />
          <Field label={<span className="font-medium text-ink">Landed cost</span>} value={<b>{nok(d.price.landed_nok)}</b>} />
          <div className="mt-2 text-xs text-ink-3">
            {sourceLabel(d.source)} · seller {d.seller ?? "?"} · {d.seller_country ?? "??"} ({d.seller_region ?? "unknown region"}) ·{" "}
            {d.condition ?? "condition ?"}
          </div>
          <div className="mt-1 text-[11px] text-ink-3">Shipping and import buffer are estimates, not exact tax.</div>
        </Block>

        {/* MARKET */}
        <Block title="Market" icon={<span className="text-gold">2</span>}>
          {m ? (
            <>
              <Field label="Market low" value={nok(m.low)} />
              <Field label="Cheapest 3 (median)" value={nok(m.cheapest3)} />
              <Field label="Cheapest 5 (median)" value={nok(m.cheapest5)} />
              <Field label="Cheapest 10 (median)" value={nok(m.cheapest10)} />
              <div className="my-1 border-t border-line" />
              <Field label={<span className="font-medium text-ink">Fair value</span>} value={<b className="text-gold">{nok(d.fair_value_nok)}</b>} />
              <Field label="Fair-value range" value={`${nok(d.fair_value_low)} – ${nok(d.fair_value_high)}`} />
              <Field label="Valid / excluded listings" value={`${m.valid_listings} / ${m.excluded_listings ?? "—"}`} />
              <Field label="Broad / trimmed median" value={`${nok(m.broad_median)} · ${nok(m.trimmed_median)}`} className="text-ink-3" />
              <div className="mt-2 flex flex-wrap gap-1">
                {m.has_expensive_tail && <Badge tone="info">expensive tail ignored</Badge>}
                {d.fair_value_flags
                  .filter((f) => f !== "market_has_expensive_tail")
                  .map((f) => (
                    <Badge key={f} tone="warn">
                      {f.replace(/_/g, " ")}
                    </Badge>
                  ))}
              </div>
              <div className="mt-2 text-[11px] text-ink-3">Observed {rel(m.observed_at)} · {dt(m.observed_at)}</div>
            </>
          ) : (
            <div className="text-sm text-ink-3">No market snapshot for this item.</div>
          )}
        </Block>

        {/* DECISION */}
        <Block title="Decision" icon={<span className="text-gold">3</span>}>
          <Field label="Raw score" value={num(d.score, 1)} />
          <Field label="Score band" value={<LevelBadge level={d.raw_band} />} />
          <Field label="Effective level" value={<LevelBadge level={d.level} />} />
          <Field label="Discount (landed)" value={<span className={gainClass(d.discount_pct)}>{pct(d.discount_pct)}</span>} />
          {d.item_discount_pct !== null && <Field label="Discount (item only)" value={pct(d.item_discount_pct)} />}
          <Field label="Confidence" value={pct(d.confidence, 0)} />
          <Field label="Match" value={`${d.match.status} · ${pct(d.match.confidence, 0)}`} />
          <div className="mt-3 rounded-lg border border-line bg-surface p-2.5 text-xs">
            {n === null ? (
              <div className="flex items-start gap-2 text-ink-3">
                <Info size={14} className="mt-px shrink-0" /> No alert decision recorded (last evaluated with alerts off).
              </div>
            ) : n.notify ? (
              <div className="flex items-start gap-2 text-emerald-300">
                <BellRing size={14} className="mt-px shrink-0" /> Alert qualifies ({n.severity?.replace("_", " ").toLowerCase()}).
              </div>
            ) : (
              <div className="text-ink-2">
                <div className="flex items-center gap-2">
                  <Ban size={14} className="shrink-0 text-ink-3" /> Not alerted
                </div>
                <ul className="mt-1 list-disc pl-5 text-ink-3">
                  {n.blocked_by.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </Block>
      </div>

      {/* Why */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Block title="Why it scores" icon={<CircleCheck size={13} className="text-gain" />}>
          {d.reasons.length ? <Notes items={d.reasons} tone="gain" /> : <div className="text-sm text-ink-3">No positive signals.</div>}
          {(d.caps.length > 0 || d.warnings.length > 0) && (
            <>
              <h4 className="mt-4 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                <ShieldAlert size={13} className="text-warn" /> Caps & caveats
              </h4>
              <Notes items={[...d.caps, ...d.warnings.filter((w) => !d.caps.includes(w))]} tone="warn" />
            </>
          )}
          {d.fair_value_explanation.length > 0 && (
            <>
              <h4 className="mt-4 text-[11px] font-semibold uppercase tracking-wider text-ink-3">How fair value was set</h4>
              <Notes items={d.fair_value_explanation} tone="info" />
            </>
          )}
        </Block>

        <Block title="Score components" icon={<span className="text-gold">Σ</span>}>
          <div className="space-y-2">
            {Object.entries(d.components).map(([k, v]) => (
              <div key={k}>
                <div className="flex justify-between text-xs">
                  <span className="text-ink-2">{COMPONENT_LABEL[k] ?? k.replace(/_/g, " ")}</span>
                  <span className="num text-ink-3">
                    {num(d.weighted[k], 1)} pts · {pct(v, 0)}
                  </span>
                </div>
                <ProgressBar value={v} tone="info" className="mt-1 h-1.5" />
              </div>
            ))}
          </div>
          {Object.keys(d.modifiers).length > 0 && (
            <div className="mt-3 border-t border-line pt-2">
              {Object.entries(d.modifiers).map(([k, v]) => (
                <Field key={k} label={k.replace(/_/g, " ")} value={<span className={gainClass(v)}>{v > 0 ? `+${num(v, 1)}` : num(v, 1)}</span>} />
              ))}
            </div>
          )}
        </Block>
      </div>
      <div className="text-[11px] text-ink-3">Evaluated {rel(d.evaluated_at)} ({dt(d.evaluated_at)}) · listing #{d.listing_id}</div>
    </div>
  );
}

/** Right-hand drawer on desktop, full-screen sheet on phones. */
export default function DealDetailSheet({ listingId, onClose }: { listingId: number; onClose: () => void }) {
  const { data, error, loading } = useApi<DealDetail>(`dashboard/deals/${listingId}`);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Deal detail">
      <button className="absolute inset-0 hidden bg-black/60 sm:block" aria-label="Close" onClick={onClose} />
      <div className="absolute inset-0 flex flex-col bg-canvas sm:inset-y-0 sm:left-auto sm:right-0 sm:w-[min(980px,92vw)] sm:border-l sm:border-line">
        <div className="flex items-center justify-between border-b border-line bg-surface px-4 py-3">
          <div className="text-sm font-semibold text-ink">Deal detail</div>
          <button className="rounded-lg p-2 text-ink-2 hover:bg-surface-2" onClick={onClose} aria-label="Close detail">
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-4 pb-safe sm:px-6">
          <ErrorBox error={error} />
          <Loading show={loading && !data} />
          {data && <DetailBody d={data} />}
        </div>
      </div>
    </div>
  );
}

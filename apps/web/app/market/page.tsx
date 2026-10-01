"use client";

import { Activity, ArrowDownRight, ArrowUpRight, Database, Flame, LineChart, TrendingUp, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback } from "react";
import { EntityCell, entitySub, entityTitle } from "@/components/deals/bits";
import EntitySearch from "@/components/EntitySearch";
import PriceHistoryChart, { type PricePoint } from "@/components/market/PriceHistoryChart";
import {
  Badge,
  CardThumb,
  Disclosure,
  EmptyState,
  ErrorBox,
  Field,
  HistoryPending,
  KpiCard,
  LevelBadge,
  Loading,
  PageHeader,
  Panel,
  btnGhost,
} from "@/components/ui";
import { useApi } from "@/lib/api";
import type { Market, MarketSeries, Mover } from "@/lib/dashboard";
import { day, dt, gainClass, nok, pct, rel } from "@/lib/format";

function hhmm(ts: string): string {
  const d = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(ts) ? ts : `${ts}Z`);
  return d.toLocaleString("nb-NO", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function SeriesPanel({ type, id, onClear }: { type: string; id: number; onClear: () => void }) {
  const { data, error, loading } = useApi<MarketSeries>(`dashboard/market/series/${type}/${id}?days=90`);
  const title = data ? entityTitle(data.entity) : "Loading…";
  const daily: PricePoint[] = (data?.daily ?? []).map((d) => ({ label: day(d.day), low: d.low, c5: d.cheapest5, fair: d.fair_value }));
  const intraday: PricePoint[] = (data?.intraday ?? []).map((s) => ({ label: hhmm(s.timestamp), low: s.low, c5: s.cheapest5 }));
  const cur = data?.current;
  const fv = data?.fair_value;

  return (
    <Panel
      title={
        <span className="flex min-w-0 items-center gap-2">
          <LineChart size={15} className="text-ink-3" /> Price history · <span className="truncate">{title}</span>
        </span>
      }
      actions={
        <button className={btnGhost} onClick={onClear} aria-label="Clear selection">
          <X size={14} /> Clear
        </button>
      }
    >
      <ErrorBox error={error} />
      <Loading show={loading && !data} />
      {data && (
        <div className="grid gap-4 lg:grid-cols-[280px_1fr] [&>*]:min-w-0">
          <div className="space-y-3">
            <div className="flex gap-3">
              <CardThumb src={data.entity.image_url} alt={title} size="lg" className="hidden sm:block" />
              <CardThumb src={data.entity.image_url} alt={title} className="sm:hidden" />
              <div className="min-w-0 sm:hidden">
                <div className="font-medium text-ink">{title}</div>
                <div className="text-xs text-ink-3">{entitySub(data.entity)}</div>
              </div>
            </div>
            <div className="hidden sm:block">
              <div className="font-medium text-ink">{title}</div>
              <div className="text-xs text-ink-3">{entitySub(data.entity)}</div>
            </div>
            <div className="rounded-lg border border-line bg-surface-2 p-3">
              <Field label="Fair value" value={<b className="text-gold">{nok(fv?.value_nok)}</b>} />
              <Field label="Range" value={`${nok(fv?.low)} – ${nok(fv?.high)}`} />
              <Field label="Confidence" value={pct(fv?.confidence, 0)} />
              <div className="my-1 border-t border-line" />
              <Field label="Market low" value={nok(cur?.low)} />
              <Field label="Cheapest-5" value={nok(cur?.cheapest5)} />
              <Field label="Cheapest-10" value={nok(cur?.cheapest10)} />
              <Field label="Valid listings" value={cur?.valid_listings ?? "—"} />
              <Field label="30d trend" value={<span className={gainClass(data.history.trend_30d)}>{data.history.trend_30d === null ? "—" : pct(data.history.trend_30d, 1, true)}</span>} />
              {cur && <div className="mt-1 text-[11px] text-ink-3">Observed {rel(cur.observed_at)}</div>}
            </div>
            {fv && fv.flags.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {fv.flags.map((f) => (
                  <Badge key={f} tone="warn">
                    {f.replace(/_/g, " ")}
                  </Badge>
                ))}
              </div>
            )}
          </div>
          <div className="min-w-0">
            {data.history_ready ? (
              <>
                <div className="mb-1 text-xs text-ink-3">Daily values over the last 90 days (fair value = median of that day&apos;s evaluations).</div>
                <PriceHistoryChart data={daily} />
              </>
            ) : intraday.length >= 2 ? (
              <>
                <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-ink-3">
                  <Badge tone="info">Last 7 days, per scan</Badge>
                  Daily history needs ≥ 2 collected days ({data.daily.length} so far). Fair value shown as today&apos;s value.
                </div>
                <PriceHistoryChart data={intraday} fairNow={fv?.value_nok} />
              </>
            ) : (
              <HistoryPending what="Price history" detail="This item needs at least two scans before a chart can be drawn." />
            )}
            <div className="mt-3">
              <Disclosure title="Show data table">
                <div className="max-h-64 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="text-ink-3">
                      <tr>
                        <th className="py-1 text-left font-medium">{data.history_ready ? "Day" : "Scan"}</th>
                        <th className="py-1 text-right font-medium">Low</th>
                        <th className="py-1 text-right font-medium">Cheapest-5</th>
                        <th className="py-1 text-right font-medium">Fair value</th>
                      </tr>
                    </thead>
                    <tbody className="num">
                      {(data.history_ready ? daily : intraday).map((p, i) => (
                        <tr key={`${p.label}-${i}`} className="border-t border-line/60">
                          <td className="py-1 text-ink-2">{p.label}</td>
                          <td className="py-1 text-right">{nok(p.low)}</td>
                          <td className="py-1 text-right">{nok(p.c5)}</td>
                          <td className="py-1 text-right">{nok(p.fair ?? null)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Disclosure>
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
}

function MoverList({ rows, up, select }: { rows: Mover[]; up: boolean; select: (t: string, id: number) => void }) {
  if (!rows.length) return <div className="px-4 py-6 text-center text-sm text-ink-3">No {up ? "increases" : "decreases"} in the collected window.</div>;
  return (
    <ul className="divide-y divide-line/70">
      {rows.map((m) => (
        <li key={`${m.entity_type}-${m.entity_id}`}>
          <button className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-surface-2" onClick={() => select(m.entity_type, m.entity_id)}>
            <EntityCell entity={m.entity} />
            <div className="num shrink-0 text-right">
              <div className={`text-sm font-medium ${gainClass(m.change_pct)}`}>{pct(m.change_pct, 1, true)}</div>
              <div className="text-[11px] text-ink-3">
                {nok(m.from_nok)} → {nok(m.to_nok)}
              </div>
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}

function MarketView() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const selType = params.get("type");
  const selId = params.get("id") ? Number(params.get("id")) : null;
  const { data, error, loading } = useApi<Market>("dashboard/market");

  const select = useCallback(
    (type: string | null, id: number | null) => {
      const sp = new URLSearchParams(params.toString());
      if (type && id) {
        sp.set("type", type);
        sp.set("id", String(id));
      } else {
        sp.delete("type");
        sp.delete("id");
      }
      const s = sp.toString();
      router.replace(s ? `${pathname}?${s}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  const c = data?.coverage;
  return (
    <>
      <PageHeader title="Market" icon={TrendingUp} subtitle="What the collected CardTrader data says right now. History only covers days the system has actually observed." />
      <ErrorBox error={error} />
      <Loading show={loading && !data} />
      {data && c && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 [&>*]:min-w-0">
            <KpiCard label="Observations" value={c.observations.toLocaleString("nb-NO")} icon={Database} hint={`since ${dt(c.first_observation)}`} />
            <KpiCard label="Tracked items" value={c.tracked_entities.toLocaleString("nb-NO")} hint={`${c.tracked_cards} cards · ${c.tracked_products} products`} />
            <KpiCard label="Days of history" value={c.days_collected} hint={c.first_day ? `UTC days ${day(c.first_day)} – ${day(c.last_day)}` : "none yet"} icon={Activity} />
            <KpiCard label="Items with ≥ 7 days" value={c.entities_with_7_days.toLocaleString("nb-NO")} hint="needed for meaningful trends" />
          </div>

          {/* Selected card chart */}
          {selType && selId ? (
            <SeriesPanel type={selType} id={selId} onClear={() => select(null, null)} />
          ) : (
            <Panel title="Price history" icon={LineChart} subtitle="Pick a card or product to chart market low, cheapest-5 and fair value.">
              <div className="max-w-xl">
                <EntitySearch onPick={(p) => select(p.entity_type, p.entity_id)} placeholder="Search a card or product…" />
              </div>
              {data.most_liquid.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  <span className="text-xs text-ink-3">Quick picks:</span>
                  {data.most_liquid.slice(0, 6).map((m) => (
                    <button key={`${m.entity_type}-${m.entity_id}`} className="rounded-full border border-line px-2.5 py-0.5 text-xs text-ink-2 hover:border-line-strong hover:text-ink" onClick={() => select(m.entity_type, m.entity_id)}>
                      {entityTitle(m.entity)}
                    </button>
                  ))}
                </div>
              )}
            </Panel>
          )}

          {/* Movers */}
          {data.movers_ready ? (
            <div className="grid gap-4 lg:grid-cols-2 [&>*]:min-w-0">
              <Panel title="Biggest increases" icon={ArrowUpRight} subtitle={`Cheapest-5 change over the collected window (items ≥ ${nok(c.min_value_nok)})`} bodyClassName="">
                <MoverList rows={data.gainers} up select={select} />
              </Panel>
              <Panel title="Biggest decreases" icon={ArrowDownRight} subtitle={`Cheapest-5 change over the collected window (items ≥ ${nok(c.min_value_nok)})`} bodyClassName="">
                <MoverList rows={data.decliners} up={false} select={select} />
              </Panel>
            </div>
          ) : (
            <Panel title="Price movers" icon={TrendingUp}>
              <HistoryPending
                what="Price-change history"
                detail={
                  <>
                    Movers need at least two collected days per item. So far: {c.days_collected} day{c.days_collected === 1 ? "" : "s"} ({c.first_day ? day(c.first_day) : "—"}). Nothing is
                    back-filled.
                  </>
                }
              />
            </Panel>
          )}

          <div className="grid gap-4 lg:grid-cols-2 [&>*]:min-w-0">
            <Panel title="Most liquid tracked items" icon={Activity} subtitle={`Most valid listings right now (cheapest-5 ≥ ${nok(c.min_value_nok)})`} bodyClassName="">
              {data.most_liquid.length ? (
                <ul className="divide-y divide-line/70">
                  {data.most_liquid.map((m) => (
                    <li key={`${m.entity_type}-${m.entity_id}`}>
                      <button className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-surface-2" onClick={() => select(m.entity_type, m.entity_id)}>
                        <EntityCell entity={m.entity} />
                        <div className="num shrink-0 text-right">
                          <div className="text-sm text-ink">{m.valid_listings} listings</div>
                          <div className="text-[11px] text-ink-3">c5 {nok(m.cheapest5)}</div>
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState title="No market snapshots yet" />
              )}
            </Panel>
            <Panel title="Strongest discounts now" icon={Flame} subtitle="Active listings furthest below fair value (landed cost)" bodyClassName="">
              {data.strongest_discounts.length ? (
                <ul className="divide-y divide-line/70">
                  {data.strongest_discounts.map((d) => (
                    <li key={d.listing_id}>
                      <Link href={`/deals?listing=${d.listing_id}`} className="flex items-center justify-between gap-3 px-4 py-2.5 hover:bg-surface-2">
                        <EntityCell entity={d.entity} fallback={d.title} />
                        <div className="num flex shrink-0 items-center gap-3 text-right">
                          <div>
                            <div className={`text-sm font-medium ${gainClass(d.discount_pct)}`}>{pct(d.discount_pct)}</div>
                            <div className="text-[11px] text-ink-3">{nok(d.price.landed_nok)}</div>
                          </div>
                          <span className="hidden sm:inline">
                            <LevelBadge level={d.level} />
                          </span>
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState title="No active listings below fair value" />
              )}
            </Panel>
          </div>
        </div>
      )}
    </>
  );
}

export default function MarketPage() {
  return (
    <Suspense fallback={<Loading />}>
      <MarketView />
    </Suspense>
  );
}

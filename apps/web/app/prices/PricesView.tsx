"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { PriceChart } from "@/components/Charts";
import EntitySearch from "@/components/EntitySearch";
import { Empty, ErrorBox, Loading, PageHeader, Panel, StatTile } from "@/components/ui";
import { qs, useApi } from "@/lib/api";
import { dt, nok, num, pct } from "@/lib/format";
import type { PriceHistory } from "@/lib/types";

export default function PricesView() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const type = params.get("type") === "product" ? "product" : "card";
  const id = params.get("id");
  const days = params.get("days") ?? "90";
  const valid = id && /^\d+$/.test(id);
  const { data, error, loading } = useApi<PriceHistory>(valid ? `prices/${type}/${id}${qs({ days })}` : null);

  const go = (t: string, i: number, d = days) => router.push(`${pathname}${qs({ type: t, id: i, days: d })}`);

  return (
    <>
      <PageHeader title="Price history" subtitle="Daily aggregates of our own snapshots, plus the current fair-value estimate." />
      <Panel className="mb-6">
        <div className="grid gap-2 md:grid-cols-4">
          <div className="md:col-span-3">
            <EntitySearch onPick={(p) => go(p.entity_type, p.entity_id)} />
          </div>
          <select
            className="rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            value={days}
            disabled={!valid}
            onChange={(e) => valid && go(type, Number(id), e.target.value)}
          >
            <option value="7">7 days</option>
            <option value="30">30 days</option>
            <option value="90">90 days</option>
            <option value="365">1 year</option>
            <option value="3650">All</option>
          </select>
        </div>
      </Panel>
      <ErrorBox error={error} />
      {!valid && <Empty>Search for a card or product to see its price history.</Empty>}
      <Loading show={!!valid && loading && !data} />
      {data && (
        <div className="space-y-6">
          <div>
            <h2 className="text-lg font-semibold">{data.label}</h2>
            <div className="text-sm text-zinc-500">{data.set_name}</div>
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            <StatTile
              label="Fair value"
              value={nok(data.fair_value.fair_value_nok)}
              hint={`${nok(data.fair_value.fair_value_low)} – ${nok(data.fair_value.fair_value_high)}`}
            />
            <StatTile label="Confidence" value={num(data.fair_value.confidence, 2)} />
            <StatTile label="7d median" value={nok(data.history.median_7d)} />
            <StatTile label="30d median" value={nok(data.history.median_30d)} hint={`${data.history.days_30d} days of data`} />
            <StatTile label="90d median" value={nok(data.history.median_90d)} />
            <StatTile label="30d trend" value={pct(data.history.trend_30d, 1, true)} />
            <StatTile label="Volatility" value={num(data.history.volatility_30d, 3)} hint="σ daily log returns" />
          </div>
          <Panel title="Daily market">
            {data.daily.length ? <PriceChart data={data} /> : <Empty>No daily aggregates yet — they build up as collectors run.</Empty>}
          </Panel>
          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="Fair value explanation">
              <ul className="list-disc pl-5 text-sm">
                {data.fair_value.explanation.map((e) => <li key={e}>{e}</li>)}
              </ul>
              <div className="mt-3 text-xs text-zinc-500">
                Current: low {nok(data.current.low)} · cheapest-5 median {nok(data.current.cheapest5_median)} · trimmed median{" "}
                {nok(data.current.trimmed_median)} · {data.current.listing_count} listings · dispersion {num(data.current.dispersion, 2)}
              </div>
            </Panel>
            <Panel title="Your purchases">
              {data.portfolio_entries.length === 0 ? (
                <Empty>Not in your portfolio.</Empty>
              ) : (
                <ul className="space-y-1 text-sm">
                  {data.portfolio_entries.map((e, i) => (
                    <li key={i}>
                      {e.quantity} × {nok(e.price_nok)} {e.date ? `on ${e.date}` : ""}
                    </li>
                  ))}
                </ul>
              )}
              {data.raw.length > 0 && (
                <div className="mt-3 text-xs text-zinc-500">Last raw snapshot: {dt(data.raw[data.raw.length - 1].timestamp)}</div>
              )}
            </Panel>
          </div>
        </div>
      )}
    </>
  );
}

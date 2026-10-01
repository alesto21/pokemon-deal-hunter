"use client";

import { Info, Package, Plus, RefreshCw } from "lucide-react";
import Link from "next/link";
import { entitySub, UnpricedNote } from "@/components/portfolio/common";
import {
  Badge,
  btnGhost,
  btnPrimary,
  CardThumb,
  type Column,
  DataTable,
  Delta,
  EmptyState,
  ErrorBox,
  KpiCard,
  Loading,
  PageHeader,
  Panel,
} from "@/components/ui";
import { useApi } from "@/lib/api";
import type { Sealed, SealedRow } from "@/lib/dashboard";
import { day, nok, num } from "@/lib/format";

function Score({ label, v, higher }: { label: string; v: number; higher: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-9 text-[11px] text-ink-3">{label}</span>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-surface-3">
        <div className={`h-full rounded-full ${higher ? "bg-gold" : "bg-ink-3"}`} style={{ width: `${Math.round(v * 100)}%` }} />
      </div>
      <span className={`num text-xs ${higher ? "text-ink" : "text-ink-3"}`}>{num(v, 2)}</span>
    </div>
  );
}

function Scores({ r }: { r: SealedRow }) {
  if (!r.analysis) return <span className="text-xs text-ink-3">needs a market price</span>;
  const { rip_score: rip, hold_score: hold } = r.analysis;
  return (
    <div className="space-y-1">
      <Score label="Rip" v={rip} higher={rip > hold} />
      <Score label="Hold" v={hold} higher={hold >= rip} />
    </div>
  );
}

const COLUMNS: Column<SealedRow>[] = [
  {
    key: "product",
    header: "Product",
    cell: (r) => (
      <div className="flex items-center gap-3">
        <CardThumb src={r.entity?.image_url} alt={r.entity?.name ?? ""} size="sm" />
        <div className="min-w-0">
          <div className="truncate text-ink">
            {r.entity?.name}
            {r.quantity > 1 && <span className="ml-1 text-ink-3">×{r.quantity}</span>}
          </div>
          <div className="truncate text-xs text-ink-3">{entitySub(r.entity)}</div>
        </div>
      </div>
    ),
  },
  { key: "packs", header: "Packs", align: "right", cell: (r) => (r.packs ?? "—") },
  {
    key: "paid",
    header: "Paid / unit",
    align: "right",
    cell: (r) => (
      <div>
        <div>{nok(r.acquisition_price_nok)}</div>
        <div className="text-xs text-ink-3">{day(r.acquisition_date)}</div>
      </div>
    ),
  },
  { key: "value", header: "Market value", align: "right", cell: (r) => (r.value_priced ? nok(r.value_nok) : <span className="text-ink-3">No price</span>) },
  { key: "pl", header: "P/L", align: "right", cell: (r) => <Delta nokValue={r.gain_nok} pctValue={r.gain_pct} /> },
  {
    key: "ppp",
    header: "NOK / pack",
    align: "right",
    hideBelow: "lg",
    cell: (r) => (
      <div>
        <div>{nok(r.nok_per_pack_now)} <span className="text-xs text-ink-3">now</span></div>
        <div className="text-xs text-ink-3">{nok(r.nok_per_pack_acquired)} paid</div>
      </div>
    ),
  },
  { key: "scores", header: "Rip / hold", hideBelow: "lg", cell: (r) => <Scores r={r} /> },
];

function mobileCard(r: SealedRow) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3">
        <CardThumb src={r.entity?.image_url} alt={r.entity?.name ?? ""} size="sm" />
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm text-ink">
            {r.entity?.name}
            {r.quantity > 1 && <span className="ml-1 text-ink-3">×{r.quantity}</span>}
          </div>
          <div className="truncate text-xs text-ink-3">{entitySub(r.entity)}</div>
        </div>
        <div className="shrink-0 text-right text-xs">
          <div className="num text-sm text-ink">{r.value_priced ? nok(r.value_nok) : "No price"}</div>
          <Delta pctValue={r.gain_pct} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-x-4 text-xs text-ink-3">
        <span>Packs <span className="num text-ink-2">{r.packs ?? "—"}</span></span>
        <span className="text-right">Paid <span className="num text-ink-2">{nok(r.acquisition_price_nok)}</span></span>
        <span>Per pack now <span className="num text-ink-2">{nok(r.nok_per_pack_now)}</span></span>
        <span className="text-right">paid <span className="num text-ink-2">{nok(r.nok_per_pack_acquired)}</span></span>
      </div>
      <Scores r={r} />
    </div>
  );
}

export default function SealedPage() {
  const { data, error, loading, reload } = useApi<Sealed>("dashboard/sealed");
  const s = data?.summary;
  const empty = data && data.items.length === 0;
  return (
    <>
      <PageHeader
        title="Sealed"
        icon={Package}
        subtitle="Booster boxes, ETBs, bundles and other sealed product — valued at live market prices"
        actions={
          <button className={btnGhost} onClick={reload} disabled={loading}>
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        }
      />
      <ErrorBox error={error} />
      <Loading show={loading && !data} />
      {data && s && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <KpiCard label="Sealed cost" value={empty ? "—" : nok(s.cost_nok)} hint="acquisition" />
            <KpiCard label="Current value" tone={empty ? null : "gold"} value={empty ? "—" : nok(s.value_nok)} hint="live market" />
            <KpiCard label="Unrealised P/L" tone={empty ? null : s.gain_nok > 0 ? "gain" : s.gain_nok < 0 ? "loss" : null}
              value={empty ? "—" : `${s.gain_nok > 0 ? "+" : ""}${nok(s.gain_nok)}`} hint={<Delta pctValue={s.gain_pct} />} />
            <KpiCard label="Products" value={s.products} hint={`${s.count} unit${s.count === 1 ? "" : "s"}`} />
            <KpiCard label="Total packs" value={s.total_packs || "—"} hint="across all units" />
          </div>
          <UnpricedNote count={s.unpriced} />
          <Panel
            title="Sealed holdings"
            actions={
              <Badge tone="neutral" title="Rip score: how attractive opening is (price vs loose packs, set desirability, chase cards). Hold score: long-term sealed appeal (set desirability, age, trend, sealed premium). Scores are 0–1 comparisons, not expected value — no pull-rate EV data is used.">
                <Info size={11} /> About rip / hold scores
              </Badge>
            }
          >
            {empty ? (
              <EmptyState icon={Package} title="No sealed product yet"
                action={<Link href="/portfolio?add=1" className={btnPrimary}><Plus size={15} /> Add sealed product</Link>}>
                Add booster boxes, ETBs or bundles you own. Per-pack cost and rip/hold scores are calculated from live prices.
              </EmptyState>
            ) : (
              <DataTable rows={data.items} columns={COLUMNS} rowKey={(r) => r.id} mobileCard={mobileCard} />
            )}
          </Panel>
          {!empty && (
            <p className="text-xs text-ink-3">
              Rip and hold are relative 0–1 scores from the backend sealed analysis; the higher of the two is highlighted.
              They are not an expected-value estimate — no pull-rate data is used.
            </p>
          )}
        </div>
      )}
    </>
  );
}

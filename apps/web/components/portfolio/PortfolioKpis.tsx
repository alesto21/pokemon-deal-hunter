"use client";

import { Coins, Layers, Package, Percent, Sparkles, TrendingUp, Wallet } from "lucide-react";
import { Delta, KpiCard } from "@/components/ui";
import type { Group, PortfolioOverview } from "@/lib/dashboard";
import { nok, pct } from "@/lib/format";

function tone(v: number | null | undefined): "gain" | "loss" | null {
  if (!v) return null;
  return v > 0 ? "gain" : "loss";
}

/** Value / cost / P&L tiles. `empty` renders dashes instead of misleading zeros. */
export function PortfolioKpis({ p, compact = false }: { p: PortfolioOverview; compact?: boolean }) {
  const s = p.summary;
  const empty = s.item_count === 0;
  const dash = "—";
  return (
    <>
      <KpiCard label="Market value" icon={Wallet} tone={empty ? null : "gold"} value={empty ? dash : nok(s.total_value_nok)}
        hint={empty ? "No holdings yet" : `Raw ${nok(s.raw_value_nok)} · Graded ${nok(s.graded_value_nok)}`} />
      <KpiCard label="Acquisition cost" icon={Coins} value={empty ? dash : nok(s.total_cost_nok)} hint={empty ? "Add purchases to track cost" : "What you paid"} />
      <KpiCard label="Unrealised P/L" icon={TrendingUp} tone={empty ? null : tone(s.unrealized_gain_nok)}
        value={empty ? dash : `${s.unrealized_gain_nok > 0 ? "+" : ""}${nok(s.unrealized_gain_nok)}`}
        hint={s.change_30d_nok !== null ? <>30 days: <Delta nokValue={s.change_30d_nok} /></> : "30-day change after 30 days of snapshots"} />
      <KpiCard label="Unrealised P/L %" icon={Percent} tone={empty ? null : tone(s.unrealized_gain_pct)}
        value={empty || s.unrealized_gain_pct === null ? dash : pct(s.unrealized_gain_pct, 1, true)} hint="vs acquisition cost" />
      {!compact && (
        <KpiCard label="Items" icon={Layers} value={s.item_count} hint={`${p.by_kind.raw.count} raw · ${p.by_kind.graded.count} graded · ${p.by_kind.sealed.count} sealed`} />
      )}
    </>
  );
}

const KINDS: { key: "raw" | "graded" | "sealed"; label: string; icon: typeof Wallet }[] = [
  { key: "raw", label: "Raw cards", icon: Sparkles },
  { key: "graded", label: "Graded cards", icon: Layers },
  { key: "sealed", label: "Sealed", icon: Package },
];

/** Three-way split so cards, graded slabs and sealed product are never blurred together. */
export function KindBreakdown({ byKind }: { byKind: PortfolioOverview["by_kind"] }) {
  return (
    <div className="grid grid-cols-1 divide-y divide-line rounded-xl border border-line bg-surface sm:grid-cols-3 sm:divide-x sm:divide-y-0">
      {KINDS.map(({ key, label, icon: Icon }) => {
        const g: Group = byKind[key];
        return (
          <div key={key} className="flex items-center justify-between gap-3 px-4 py-3">
            <div className="flex min-w-0 items-center gap-2.5">
              <Icon size={15} className="shrink-0 text-ink-3" />
              <div className="min-w-0">
                <div className="text-xs text-ink-3">{label}</div>
                <div className="num text-sm text-ink">
                  {g.count ? `${g.count} · ${nok(g.value_nok)}` : <span className="text-ink-3">None yet</span>}
                </div>
              </div>
            </div>
            {g.count > 0 && (
              <div className="shrink-0 text-right text-xs">
                <Delta pctValue={g.gain_pct} />
                {g.unpriced > 0 && <div className="text-amber-300/80">{g.unpriced} unpriced</div>}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

import { nok } from "@/lib/format";
import type { DealRow } from "@/lib/dashboard";

type Price = DealRow["price"];

/** True when any part of the delivered cost is an estimate (not seller-stated / checkout-observed). */
export function isEstimated(p: Price): boolean {
  return p.shipping_basis !== "exact" || p.fees_basis !== "exact";
}

/** Amount + basis label. Estimates get an amber dashed underline and an "est." tag — never look exact. */
export function CostValue({ value, basis }: { value: number; basis: string }) {
  if (basis === "exact") {
    return (
      <span className="num">
        {nok(value)} <span className="text-[10px] uppercase tracking-wide text-ink-3">quote</span>
      </span>
    );
  }
  return (
    <span className="num">
      <span className="border-b border-dashed border-amber-400/70">{nok(value)}</span>{" "}
      <span className="text-[10px] uppercase tracking-wide text-amber-300">est.</span>
    </span>
  );
}

/** Landed cost; "≈" prefix when estimated. */
export function LandedValue({ p, className = "" }: { p: Price; className?: string }) {
  return (
    <span className={`num ${className}`}>
      {isEstimated(p) && <span className="text-amber-300">≈ </span>}
      {nok(p.landed_nok)}
    </span>
  );
}

export function routeLabel(route: string | null | undefined): string | null {
  return route === "direct" ? "Direct seller shipment" : route === "zero" ? "CardTrader Zero" : null;
}

/** One-line honesty note under any delivered-cost breakdown. */
export function CostNote({ p }: { p: Price }) {
  const conf = p.landed_cost_confidence;
  return (
    <div className={`mt-1 text-[11px] ${isEstimated(p) ? "text-amber-300/90" : "text-ink-3"}`}>
      {isEstimated(p) ? "Shipping estimate — verify at checkout" : "Shipping from an observed checkout quote"}
      {conf !== null && conf !== undefined && ` · landed-cost confidence ${Math.round(conf * 100)}%`}
      {routeLabel(p.purchase_route) && ` · ${routeLabel(p.purchase_route)}`}
    </div>
  );
}

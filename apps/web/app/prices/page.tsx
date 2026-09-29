import { Suspense } from "react";
import PricesView from "./PricesView";

export default function PricesPage() {
  return (
    <Suspense fallback={<div className="py-6 text-sm text-zinc-500">Loading…</div>}>
      <PricesView />
    </Suspense>
  );
}

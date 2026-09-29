import Link from "next/link";
import { gainClass, nok, pct } from "@/lib/format";
import type { Holding } from "@/lib/types";
import { Empty, btnDanger, td, th } from "./ui";

export function holdingLabel(h: Holding): string {
  if (h.card) return `${h.card.name} ${h.card.card_number ?? ""} (${h.card.set_name ?? "?"})`.replace(/\s+/g, " ");
  if (h.product) return h.product.name;
  return `#${h.id}`;
}

export default function HoldingsTable({ items, onDelete, compact = false }: { items: Holding[]; onDelete?: (id: number) => void; compact?: boolean }) {
  if (!items.length) return <Empty>Nothing here yet.</Empty>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px]">
        <thead className="border-b border-zinc-200 dark:border-zinc-800">
          <tr>
            <th className={th}>Item</th>
            {!compact && <th className={th}>Binder</th>}
            <th className={`${th} text-right`}>Qty</th>
            <th className={`${th} text-right`}>Cost</th>
            <th className={`${th} text-right`}>Value</th>
            <th className={`${th} text-right`}>Gain</th>
            {onDelete && <th className={th}></th>}
          </tr>
        </thead>
        <tbody>
          {items.map((h) => {
            const type = h.card_id ? "card" : "product";
            const id = h.card_id ?? h.product_id;
            return (
              <tr key={h.id} className="border-b border-zinc-100 dark:border-zinc-900">
                <td className={td}>
                  <Link className="hover:underline" href={`/prices?type=${type}&id=${id}`}>{holdingLabel(h)}</Link>
                  {!compact && (
                    <div className="text-xs text-zinc-500">
                      {h.condition ?? ""} {h.grading_status === "graded" ? `· ${h.grade_company ?? "PSA"} ${h.psa_grade ?? ""}` : h.grading_status !== "raw" ? `· ${h.grading_status}` : ""}
                      {h.acquisition_date ? ` · ${h.acquisition_date}` : ""}
                    </div>
                  )}
                </td>
                {!compact && <td className={td}>{h.binder_type}</td>}
                <td className={`${td} text-right tabular-nums`}>{h.quantity}</td>
                <td className={`${td} text-right tabular-nums`}>{nok(h.cost_nok)}</td>
                <td className={`${td} text-right tabular-nums`}>
                  {h.unit_raw_value_nok === null && h.unit_graded_value_nok === null ? "—" : nok(h.value_nok)}
                </td>
                <td className={`${td} text-right tabular-nums ${gainClass(h.gain_nok)}`}>
                  {nok(h.gain_nok)} <span className="text-xs">{pct(h.gain_pct, 0, true)}</span>
                </td>
                {onDelete && (
                  <td className={`${td} text-right`}>
                    <button className={btnDanger} onClick={() => onDelete(h.id)}>Delete</button>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

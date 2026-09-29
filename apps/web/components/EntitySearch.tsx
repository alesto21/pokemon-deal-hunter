"use client";

import { useEffect, useState } from "react";
import { api, qs } from "@/lib/api";
import type { Card, Product } from "@/lib/types";
import { input } from "./ui";

export interface EntityPick {
  entity_type: "card" | "product";
  entity_id: number;
  label: string;
}

function cardLabel(c: Card) {
  return `${c.name} ${c.card_number ?? ""} (${c.set_name ?? c.set_code ?? "?"})`.replace(/\s+/g, " ");
}

/** Debounced search over /cards and optionally /products. */
export default function EntitySearch({
  onPick,
  includeProducts = true,
  includeCards = true,
  placeholder = "Search card or product…",
}: {
  onPick: (p: EntityPick) => void;
  includeProducts?: boolean;
  includeCards?: boolean;
  placeholder?: string;
}) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<EntityPick[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (q.trim().length < 2) return;
    const t = setTimeout(async () => {
      try {
        const [cards, products] = await Promise.all([
          includeCards ? api<Card[]>(`cards${qs({ q, limit: 15 })}`) : Promise.resolve([] as Card[]),
          includeProducts ? api<Product[]>(`products${qs({ q, limit: 10 })}`) : Promise.resolve([] as Product[]),
        ]);
        setResults([
          ...cards.map((c) => ({ entity_type: "card" as const, entity_id: c.id, label: cardLabel(c) })),
          ...products.map((p) => ({ entity_type: "product" as const, entity_id: p.id, label: `${p.name} [${p.product_type}]` })),
        ]);
        setErr(null);
      } catch (e) {
        setErr((e as Error).message);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [q, includeCards, includeProducts]);

  const visible = q.trim().length < 2 ? [] : results;

  return (
    <div className="relative">
      <input className={input} value={q} placeholder={placeholder} onChange={(e) => setQ(e.target.value)} />
      {err && <div className="mt-1 text-xs text-red-600">{err}</div>}
      {visible.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-md border border-zinc-200 bg-white shadow-lg dark:border-zinc-700 dark:bg-zinc-900">
          {visible.map((r) => (
            <li key={`${r.entity_type}-${r.entity_id}`}>
              <button
                type="button"
                className="block w-full px-3 py-1.5 text-left text-sm hover:bg-zinc-100 dark:hover:bg-zinc-800"
                onClick={() => {
                  onPick(r);
                  setQ("");
                  setResults([]);
                }}
              >
                <span className="mr-2 text-xs uppercase text-zinc-400">{r.entity_type}</span>
                {r.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { api, qs } from "@/lib/api";
import type { Card, Product } from "@/lib/types";
import { CardThumb, input } from "./ui";

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
  const [results, setResults] = useState<(EntityPick & { image?: string | null })[]>([]);
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
          ...cards.map((c) => ({ entity_type: "card" as const, entity_id: c.id, label: cardLabel(c), image: c.image_url })),
          ...products.map((p) => ({
            entity_type: "product" as const,
            entity_id: p.id,
            label: `${p.name} [${p.product_type.replace("_", " ")}]`,
            image: p.image_url,
          })),
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
      {err && <div className="mt-1 text-xs text-loss">{err}</div>}
      {visible.length > 0 && (
        <ul className="absolute z-40 mt-1 max-h-72 w-full overflow-auto rounded-xl border border-line-strong bg-surface-2 p-1 shadow-2xl shadow-black/50">
          {visible.map((r) => (
            <li key={`${r.entity_type}-${r.entity_id}`}>
              <button
                type="button"
                className="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left text-sm text-ink hover:bg-surface-3"
                onClick={() => {
                  onPick({ entity_type: r.entity_type, entity_id: r.entity_id, label: r.label });
                  setQ("");
                  setResults([]);
                }}
              >
                <CardThumb src={r.image} alt={r.label} size="sm" className="!h-9 !w-7" />
                <span className="min-w-0 flex-1 truncate">{r.label}</span>
                <span className="text-[10px] uppercase tracking-wide text-ink-3">{r.entity_type}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

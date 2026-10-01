"use client";

import { CardThumb } from "@/components/ui";
import type { EntityBrief } from "@/lib/dashboard";

/** Small card/product cell: thumbnail, name + number, set. */
export function EntityCell({ entity, fallback }: { entity: EntityBrief | null; fallback?: string | null }) {
  const name = entity ? `${entity.name}${entity.number ? ` ${entity.number}` : ""}` : fallback ?? "—";
  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <CardThumb src={entity?.image_url} alt={name} size="sm" />
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-ink">{name}</div>
        <div className="truncate text-xs text-ink-3">{entity?.set_name ?? ""}</div>
      </div>
    </div>
  );
}

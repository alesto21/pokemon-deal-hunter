"use client";

import { DataTable, LevelBadge, type Column } from "@/components/ui";
import type { DealRow } from "@/lib/dashboard";
import { gainClass, nok, num, pct } from "@/lib/format";
import { ConfidenceTag, DiscountCell, EntityCell, LandedCell, OpenListing, SellerTag, TopNote, entitySub, entityTitle } from "./bits";
import { CardThumb } from "@/components/ui";

function MobileDeal({ d }: { d: DealRow }) {
  return (
    <div className="flex gap-3">
      <CardThumb src={d.entity?.image_url} alt={entityTitle(d.entity, d.title)} />
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="truncate font-medium text-ink">{entityTitle(d.entity, d.title)}</div>
            <div className="truncate text-xs text-ink-3">{entitySub(d.entity)}</div>
          </div>
          <LevelBadge level={d.level} />
        </div>
        <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
          <div>
            <div className="text-ink-3">Landed</div>
            <div className="num font-medium text-ink">{nok(d.price.landed_nok)}</div>
          </div>
          <div>
            <div className="text-ink-3">Fair value</div>
            <div className="num text-ink-2">{nok(d.fair_value_nok)}</div>
          </div>
          <div className="text-right">
            <div className="text-ink-3">Discount</div>
            <div className={`num font-medium ${gainClass(d.discount_pct)}`}>{pct(d.discount_pct)}</div>
          </div>
        </div>
        <div className="mt-1.5 flex items-center justify-between text-[11px] text-ink-3">
          <span>
            {d.seller_country ?? "??"} · {d.seller_region ?? "?"} · score {num(d.score, 1)} · conf {pct(d.confidence, 0)}
          </span>
          <OpenListing url={d.url} />
        </div>
        <TopNote deal={d} />
      </div>
    </div>
  );
}

export default function DealList({ items, onOpen, compact = false }: { items: DealRow[]; onOpen: (id: number) => void; compact?: boolean }) {
  const columns: Column<DealRow>[] = [
    {
      key: "item",
      header: "Card / product",
      cell: (d) => <EntityCell entity={d.entity} fallback={d.title} extra={<TopNote deal={d} />} />,
      className: "min-w-[260px]",
    },
    { key: "seller", header: "Source", cell: (d) => <SellerTag source={d.source} country={d.seller_country} region={d.seller_region} />, hideBelow: "lg" },
    { key: "level", header: "Level", cell: (d) => <LevelBadge level={d.level} /> },
    { key: "score", header: "Score", align: "right", cell: (d) => <span className="text-ink-2">{num(d.score, 1)}</span>, hideBelow: "lg" },
    { key: "landed", header: "Landed", align: "right", cell: (d) => <LandedCell price={d.price} /> },
    { key: "fv", header: "Fair value", align: "right", cell: (d) => <span className="whitespace-nowrap text-ink-2">{nok(d.fair_value_nok)}</span> },
    { key: "disc", header: "Discount", align: "right", cell: (d) => <DiscountCell nokValue={d.discount_nok} pctValue={d.discount_pct} /> },
    { key: "conf", header: "Conf.", align: "right", cell: (d) => <ConfidenceTag value={d.confidence} />, hideBelow: compact ? "md" : "xl" },
    { key: "open", header: "", align: "right", cell: (d) => <OpenListing url={d.url} /> },
  ];
  return (
    <DataTable
      rows={items}
      columns={columns}
      rowKey={(d) => d.listing_id}
      onRowClick={(d) => onOpen(d.listing_id)}
      mobileCard={(d) => <MobileDeal d={d} />}
    />
  );
}

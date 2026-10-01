"use client";

import { ExternalLink, Layers, List } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { sourceLabel } from "@/components/deals/bits";
import ReviewQueue from "@/components/listings/ReviewQueue";
import { Badge, CardThumb, DataTable, EmptyState, ErrorBox, LevelBadge, Loading, PageHeader, Panel, type Column, input } from "@/components/ui";
import { api, qs, useApi } from "@/lib/api";
import { nok, num, rel } from "@/lib/format";
import type { Listing } from "@/lib/types";

type Tab = "all" | "review" | "lots";
const MATCH_TONE: Record<string, "gain" | "info" | "warn" | "neutral" | "loss"> = {
  auto: "gain",
  manual: "info",
  review: "warn",
  unresolved: "neutral",
  rejected: "loss",
};

function StatusSelect({ l, onChange }: { l: Listing; onChange: (status: string) => void }) {
  return (
    <select
      className="w-[6.5rem] shrink-0 rounded-lg border border-line bg-surface-2 px-2 py-1 text-xs text-ink focus:border-line-strong focus:outline-none"
      value={l.status}
      onClick={(e) => e.stopPropagation()}
      onChange={(e) => onChange(e.target.value)}
      aria-label={`Status of listing ${l.id}`}
    >
      <option value="active">active</option>
      <option value="sold">sold</option>
      <option value="ignored">ignored</option>
      <option value="gone">gone</option>
    </select>
  );
}

function AllListings({ lotsOnly }: { lotsOnly: boolean }) {
  const [source, setSource] = useState("");
  const [status, setStatus] = useState("active");
  const [match, setMatch] = useState("");
  const [q, setQ] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const { data, error, loading, reload } = useApi<Listing[]>(
    `listings${qs({ source, status: lotsOnly ? undefined : status, match_status: lotsOnly ? undefined : match, limit: 500 })}`,
  );

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (data ?? []).filter(
      (l) => (!lotsOnly || l.listing_kind === "lot") && (!needle || `${l.title} ${l.entity_label ?? ""}`.toLowerCase().includes(needle)),
    );
  }, [data, q, lotsOnly]);

  async function setListingStatus(id: number, s: string) {
    setActionError(null);
    try {
      await api(`listings/${id}`, { method: "PATCH", json: { status: s } });
      reload();
    } catch (e) {
      setActionError((e as Error).message);
    }
  }

  const columns: Column<Listing>[] = [
    {
      key: "item",
      header: "Listing",
      cell: (l) => (
        <div className="flex min-w-0 items-center gap-3">
          {l.image_urls[0] && <CardThumb src={l.image_urls[0]} alt={l.title} size="sm" />}
          <div className="min-w-0 max-w-[16rem] xl:max-w-[24rem] 2xl:max-w-[34rem]">
            <div className="truncate font-medium text-ink" title={l.title}>
              {l.entity_label ?? l.title}
            </div>
            <div className="truncate text-xs text-ink-3" title={l.title}>
              {l.entity_label ? l.title : "not matched"}
            </div>
          </div>
        </div>
      ),
    },
    {
      key: "src",
      header: "Source",
      cell: (l) => (
        <div className="text-xs">
          <div className="text-ink-2">{sourceLabel(l.source)}</div>
          <div className="text-ink-3">
            {l.seller_country ?? "??"} · {l.seller_region ?? "?"}
          </div>
        </div>
      ),
      hideBelow: "lg",
    },
    { key: "kind", header: "Kind", cell: (l) => <Badge>{l.listing_kind}</Badge>, hideBelow: "xl" },
    {
      key: "match",
      header: "Match",
      cell: (l) => (
        <Badge tone={MATCH_TONE[l.match_status] ?? "neutral"} title={`confidence ${num(l.confidence, 2)}`}>
          {l.match_status} {num(l.confidence, 2)}
        </Badge>
      ),
    },
    { key: "landed", header: "Landed", align: "right", cell: (l) => <span className="whitespace-nowrap">{nok(l.landed_cost_nok)}</span> },
    { key: "seen", header: "Last seen", cell: (l) => <span className="whitespace-nowrap text-xs text-ink-3">{rel(l.last_seen)}</span>, hideBelow: "xl" },
    { key: "status", header: "Status", cell: (l) => <StatusSelect l={l} onChange={(s) => setListingStatus(l.id, s)} /> },
    {
      key: "actions",
      header: "",
      align: "right",
      cell: (l) => (
        <div className="flex items-center justify-end gap-3 whitespace-nowrap text-xs" onClick={(e) => e.stopPropagation()}>
          <Link className="text-ink-2 hover:text-gold" href={`/lots/${l.id}`}>
            Lot
          </Link>
          {l.url && (
            <a className="inline-flex items-center gap-1 text-ink-2 hover:text-gold" href={l.url} target="_blank" rel="noopener noreferrer">
              Open <ExternalLink size={12} />
            </a>
          )}
        </div>
      ),
    },
  ];

  return (
    <>
      <div className="mb-4 grid grid-cols-2 gap-2 rounded-xl border border-line bg-surface p-3 sm:flex sm:flex-wrap sm:items-center">
        <input className={`${input} col-span-2 sm:w-auto sm:min-w-0 sm:flex-1`} placeholder="Search title or match…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className={`${input} sm:w-40`} value={source} onChange={(e) => setSource(e.target.value)} aria-label="Source">
          <option value="">Any source</option>
          <option value="cardtrader">CardTrader</option>
          <option value="finn">FINN</option>
          <option value="manual">Manual</option>
        </select>
        {!lotsOnly && (
          <>
            <select className={`${input} sm:w-36`} value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
              <option value="active">Active</option>
              <option value="gone">Gone</option>
              <option value="sold">Sold</option>
              <option value="ignored">Ignored</option>
              <option value="">Any status</option>
            </select>
            <select className={`${input} col-span-2 sm:w-40`} value={match} onChange={(e) => setMatch(e.target.value)} aria-label="Match status">
              <option value="">Any match status</option>
              <option value="auto">Auto-matched</option>
              <option value="manual">Manually matched</option>
              <option value="review">Needs review</option>
              <option value="unresolved">Unresolved</option>
              <option value="rejected">Rejected</option>
            </select>
          </>
        )}
      </div>
      <ErrorBox error={error ?? actionError} />
      <Loading show={loading && !data} />
      {data && (
        <Panel title={`${rows.length.toLocaleString("nb-NO")} listing${rows.length === 1 ? "" : "s"}`} subtitle={data.length >= 500 ? "Showing the 500 most recently seen." : undefined} bodyClassName="p-2 sm:p-3">
          <DataTable
            rows={rows}
            columns={columns}
            rowKey={(l) => l.id}
            empty={
              lotsOnly ? (
                <EmptyState icon={Layers} title="No lots yet">
                  Open any listing&apos;s lot page (the &quot;Lot&quot; link) and create a lot breakdown to value a collection item by item.
                </EmptyState>
              ) : (
                <EmptyState icon={List} title="No listings match" />
              )
            }
            mobileCard={(l) => (
              <div className="flex gap-3">
                {l.image_urls[0] && <CardThumb src={l.image_urls[0]} alt={l.title} size="sm" />}
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate font-medium text-ink">{l.entity_label ?? l.title}</div>
                      <div className="truncate text-xs text-ink-3">
                        {sourceLabel(l.source)} · {l.seller_country ?? "??"} · {l.listing_kind}
                      </div>
                    </div>
                    <span className="num shrink-0 text-sm text-ink">{nok(l.landed_cost_nok)}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Badge tone={MATCH_TONE[l.match_status] ?? "neutral"}>
                        {l.match_status} {num(l.confidence, 2)}
                      </Badge>
                      {l.evaluation && <LevelBadge level={l.evaluation.alert_level} />}
                    </div>
                    <StatusSelect l={l} onChange={(s) => setListingStatus(l.id, s)} />
                  </div>
                  <div className="mt-2 flex gap-4 text-xs">
                    <Link className="text-ink-2" href={`/lots/${l.id}`}>
                      Lot
                    </Link>
                    {l.url && (
                      <a className="inline-flex items-center gap-1 text-ink-2" href={l.url} target="_blank" rel="noopener noreferrer">
                        Open <ExternalLink size={12} />
                      </a>
                    )}
                  </div>
                </div>
              </div>
            )}
          />
        </Panel>
      )}
    </>
  );
}

function ListingsView() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const raw = params.get("tab");
  const tab: Tab = raw === "review" || raw === "lots" ? raw : "all";
  const review = useApi<Listing[]>("review?include_unresolved=true");

  const setTab = (t: Tab) => router.replace(t === "all" ? pathname : `${pathname}?tab=${t}`, { scroll: false });
  const tabs: { value: Tab; label: string; count?: number }[] = [
    { value: "all", label: "All listings" },
    { value: "review", label: "Needs review", count: review.data?.length },
    { value: "lots", label: "Lots" },
  ];

  return (
    <>
      <PageHeader title="Listings" icon={List} subtitle="Every listing the system has seen, its match to the catalogue, and its status." />
      <div className="mb-4 flex gap-1 overflow-x-auto border-b border-line" role="tablist">
        {tabs.map((t) => (
          <button
            key={t.value}
            role="tab"
            aria-selected={tab === t.value}
            onClick={() => setTab(t.value)}
            className={`-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2 text-sm ${
              tab === t.value ? "border-gold text-ink" : "border-transparent text-ink-3 hover:text-ink-2"
            }`}
          >
            {t.label}
            {t.count !== undefined && t.count > 0 && <Badge tone="warn">{t.count}</Badge>}
          </button>
        ))}
      </div>
      {tab === "review" ? <ReviewQueue onChanged={review.reload} /> : <AllListings key={tab} lotsOnly={tab === "lots"} />}
    </>
  );
}

export default function ListingsPage() {
  return (
    <Suspense fallback={<Loading />}>
      <ListingsView />
    </Suspense>
  );
}

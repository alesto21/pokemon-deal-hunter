"use client";

import { Check, ClipboardCopy, MousePointerClick, Send } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ErrorBox, Field, LevelBadge, PageHeader, Panel, btn, btnPrimary, input } from "@/components/ui";
import { api } from "@/lib/api";
import { nok, pct } from "@/lib/format";
import type { Listing } from "@/lib/types";

/**
 * Runs in YOUR browser on a FINN ad you are already viewing. It only reads the page's public
 * meta tags (og:*, product price, JSON-LD) and opens this dashboard with the data in the URL
 * fragment (#…), which never leaves your browser. No request to FINN is made by Deal Hunter.
 */
function bookmarkletSource(origin: string): string {
  const js = `(()=>{const m=n=>{const e=document.querySelector('meta[property="'+n+'"],meta[name="'+n+'"]');return e?e.content:''};
let p=m('product:price:amount')||m('og:price:amount');
if(!p){for(const s of document.querySelectorAll('script[type="application/ld+json"]')){try{const j=JSON.parse(s.textContent);const o=[].concat(j.offers||[])[0];if(o&&o.price){p=o.price;break}}catch(e){}}}
const imgs=[...document.querySelectorAll('meta[property="og:image"]')].map(e=>e.content).slice(0,10);
const d={url:location.href.split('#')[0],title:m('og:title')||document.title,description:(m('og:description')||'').slice(0,3000),price:p,image_urls:imgs};
window.open(${JSON.stringify(origin)}+'/capture#'+encodeURIComponent(JSON.stringify(d)),'_blank')})()`;
  return `javascript:${js.replace(/\n/g, "")}`;
}

interface Form {
  url: string;
  title: string;
  price: string;
  description: string;
  shipping_nok: string;
  location: string;
  seller: string;
  seller_type: "" | "private" | "business";
  condition: string;
  image_urls: string[];
}

const EMPTY: Form = { url: "", title: "", price: "", description: "", shipping_nok: "", location: "", seller: "", seller_type: "", condition: "", image_urls: [] };

function fromHash(hash: string): Form | null {
  if (!hash || hash.length < 2) return null;
  try {
    const d = JSON.parse(decodeURIComponent(hash.slice(1)));
    const str = (v: unknown) => (typeof v === "string" || typeof v === "number" ? String(v) : "");
    return {
      ...EMPTY,
      url: str(d.url),
      title: str(d.title).replace(/\s*\|\s*FINN.*$/i, ""),
      price: str(d.price).replace(/[^\d.,]/g, "").replace(",", "."),
      description: str(d.description),
      image_urls: Array.isArray(d.image_urls) ? d.image_urls.filter((u: unknown) => typeof u === "string" && u.startsWith("https://")).slice(0, 10) : [],
    };
  } catch {
    return null;
  }
}

export default function CapturePage() {
  const [form, setForm] = useState<Form>(EMPTY);
  const [fromBookmarklet, setFromBookmarklet] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Listing | null>(null);
  const [copied, setCopied] = useState(false);
  const [source, setSource] = useState("");
  const linkRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    const src = bookmarkletSource(window.location.origin);
    // React refuses javascript: hrefs in JSX; set it on the DOM node so it can be dragged to the bookmarks bar.
    linkRef.current?.setAttribute("href", src);
    const parsed = fromHash(window.location.hash);
    // Clear the fragment so a reload does not re-submit stale data.
    if (parsed) history.replaceState(null, "", window.location.pathname);
    queueMicrotask(() => {
      setSource(src);
      if (parsed) {
        setForm(parsed);
        setFromBookmarklet(true);
      }
    });
  }, []);

  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setBusy(true);
    try {
      const body = {
        url: form.url.trim(),
        title: form.title.trim(),
        price: Number(form.price),
        description: form.description.trim() || null,
        shipping_nok: form.shipping_nok.trim() === "" ? null : Number(form.shipping_nok),
        location: form.location.trim() || null,
        seller: form.seller.trim() || null,
        seller_type: form.seller_type || null,
        condition: form.condition.trim() || null,
        image_urls: form.image_urls,
      };
      setResult(await api<Listing>("finn/capture", { method: "POST", json: body }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const ev = result?.evaluation;
  const flags = result?.safety_flags ?? [];

  return (
    <>
      <PageHeader title="Capture FINN listing" icon={MousePointerClick}
        subtitle="Add a FINN ad you are viewing in your own browser. Deal Hunter never crawls or fetches FINN." />

      <div className="grid gap-4 lg:grid-cols-5">
        <Panel title="Listing" className="lg:col-span-3"
          subtitle={fromBookmarklet ? "Prefilled from the page you captured — check every field before saving" : "Paste the details, or use the bookmarklet on a FINN ad"}>
          <form onSubmit={submit} className="space-y-3">
            <label className="block text-xs text-ink-3">FINN URL
              <input className={input} required type="url" placeholder="https://www.finn.no/recommerce/forsale/item/…" value={form.url} onChange={(e) => set("url", e.target.value)} />
            </label>
            <label className="block text-xs text-ink-3">Title
              <input className={input} required maxLength={500} value={form.title} onChange={(e) => set("title", e.target.value)} />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-xs text-ink-3">Price (NOK)
                <input className={input} required inputMode="decimal" value={form.price} onChange={(e) => set("price", e.target.value)} />
              </label>
              <label className="block text-xs text-ink-3">Shipping (NOK)
                <input className={input} inputMode="decimal" placeholder="blank = read from text / estimate" value={form.shipping_nok} onChange={(e) => set("shipping_nok", e.target.value)} />
              </label>
              <label className="block text-xs text-ink-3">Location
                <input className={input} maxLength={120} placeholder="e.g. Oslo" value={form.location} onChange={(e) => set("location", e.target.value)} />
              </label>
              <label className="block text-xs text-ink-3">Seller
                <input className={input} maxLength={200} value={form.seller} onChange={(e) => set("seller", e.target.value)} />
              </label>
              <label className="block text-xs text-ink-3">Seller type
                <select className={input} value={form.seller_type} onChange={(e) => set("seller_type", e.target.value as Form["seller_type"])}>
                  <option value="">unknown</option>
                  <option value="private">private</option>
                  <option value="business">business</option>
                </select>
              </label>
              <label className="block text-xs text-ink-3">Condition
                <input className={input} maxLength={64} placeholder="e.g. NM" value={form.condition} onChange={(e) => set("condition", e.target.value)} />
              </label>
            </div>
            <label className="block text-xs text-ink-3">Description
              <textarea className={`${input} min-h-28`} maxLength={8000} value={form.description} onChange={(e) => set("description", e.target.value)} />
            </label>
            {form.image_urls.length > 0 && <p className="text-xs text-ink-3">{form.image_urls.length} photo link(s) captured.</p>}
            <p className="text-xs text-ink-3">
              Shipping you type here is treated as exact. Left blank, it is read from the description (&quot;frakt 79 kr&quot;, &quot;fri frakt&quot;,
              &quot;kun henting&quot;) or shown as an estimate to verify.
            </p>
            <ErrorBox error={error} />
            <button className={btnPrimary} disabled={busy}><Send size={14} /> {busy ? "Saving…" : "Save & evaluate"}</button>
          </form>
        </Panel>

        <div className="space-y-4 lg:col-span-2">
          {result && (
            <Panel title="Result">
              <div className="mb-2 flex items-center gap-2">
                <LevelBadge level={ev?.alert_level ?? null} />
                <span className="truncate text-sm text-ink">{result.entity_label ?? result.title}</span>
              </div>
              <Field label="Kind" value={result.listing_kind} />
              <Field label="Match" value={`${result.match_status} · ${pct(result.confidence, 0)}`} />
              <Field label="Landed cost" value={nok(result.landed_cost_nok)} />
              <Field label="Fair value" value={nok(ev?.fair_value_nok)} />
              <Field label="Discount" value={pct(ev?.discount_pct)} />
              {flags.length > 0 && (
                <ul className="mt-2 space-y-1 text-xs text-amber-300">{flags.map((f) => <li key={f}>• {f}</li>)}</ul>
              )}
              <div className="mt-3 flex gap-2">
                <Link className={btn} href="/listings">Listings</Link>
                {result.listing_kind === "lot" && <Link className={btn} href={`/lots/${result.id}`}>Lot detail</Link>}
                {result.match_status === "review" && <Link className={btn} href="/review">Review match</Link>}
              </div>
            </Panel>
          )}
          <Panel title="Bookmarklet" subtitle="One click on a FINN ad you have open">
            <ol className="mb-3 list-decimal space-y-1 pl-4 text-xs text-ink-2">
              <li>Drag the button below to your bookmarks bar (on a phone: copy the code into a new bookmark&apos;s URL).</li>
              <li>Open a FINN ad as usual and tap the bookmark.</li>
              <li>This page opens prefilled; check the fields and save.</li>
            </ol>
            <div className="flex flex-wrap gap-2">
              <a ref={linkRef} className={btnPrimary} onClick={(e) => e.preventDefault()} title="Drag me to your bookmarks bar">
                <MousePointerClick size={14} /> Capture to Deal Hunter
              </a>
              <button className={btn} disabled={!source} onClick={async () => {
                await navigator.clipboard.writeText(source);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}>
                {copied ? <Check size={14} /> : <ClipboardCopy size={14} />} {copied ? "Copied" : "Copy code"}
              </button>
            </div>
            <p className="mt-3 text-xs text-ink-3">
              It reads only the public page you are looking at and passes it in the link fragment — nothing is sent to FINN or
              anywhere else until you press Save. The dashboard must be reachable from that browser (LAN or Tailscale).
            </p>
          </Panel>
        </div>
      </div>
    </>
  );
}

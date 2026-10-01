"use client";

import { Menu, MoreHorizontal, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SourceHealth } from "@/lib/types";
import { ALL_ITEMS, isActive, MOBILE_TABS, NAV } from "./nav";

function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-gold to-amber-700 text-sm font-black text-canvas shadow-sm">
        DH
      </span>
      <span className="leading-tight">
        <span className="block text-sm font-semibold tracking-tight text-ink">Deal Hunter</span>
        <span className="block text-[11px] text-ink-3">Pokémon collector</span>
      </span>
    </Link>
  );
}

/** Worker status in the sidebar footer: polls the light /sources endpoint once a minute. */
function useWorkerStatus() {
  const [status, setStatus] = useState<{ ok: boolean | null; label: string }>({ ok: null, label: "Checking…" });
  useEffect(() => {
    let cancelled = false;
    const load = () =>
      api<SourceHealth[]>("sources")
        .then((rows) => {
          if (cancelled) return;
          const ct = rows.find((r) => r.source === "cardtrader");
          if (!ct || !ct.enabled) setStatus({ ok: null, label: "Scanner disabled" });
          else if (ct.worker.next_scan_overdue) setStatus({ ok: false, label: "Worker overdue" });
          else if (!ct.worker.worker_scheduled) setStatus({ ok: false, label: "Worker not scheduled" });
          else if (ct.healthy === false) setStatus({ ok: false, label: "Scanner errors" });
          else setStatus({ ok: true, label: ct.running ? "Scanning now" : "Scanner healthy" });
        })
        .catch(() => !cancelled && setStatus({ ok: false, label: "API unreachable" }));
    load();
    const t = setInterval(load, 60_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);
  return status;
}

function NavLinks({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <nav className="space-y-5">
      {NAV.map((group) => (
        <div key={group.section ?? "root"}>
          {group.section && (
            <div className="mb-1.5 px-3 text-[11px] font-medium uppercase tracking-wider text-ink-3">{group.section}</div>
          )}
          <div className="space-y-0.5">
            {group.items.map(({ href, label, icon: Icon }) => {
              const active = isActive(pathname, href);
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={onNavigate}
                  className={`group flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
                    active ? "bg-surface-3 text-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink"
                  }`}
                >
                  <Icon size={16} className={active ? "text-gold" : "text-ink-3 group-hover:text-ink-2"} />
                  {label}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}

function StatusPill({ ok, label }: { ok: boolean | null; label: string }) {
  const dot = ok === null ? "bg-ink-3" : ok ? "bg-gain" : "bg-loss";
  return (
    <Link href="/system" className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-ink-2 hover:bg-surface-2">
      <span className={`h-2 w-2 rounded-full ${dot} ${ok ? "shadow-[0_0_8px] shadow-gain/60" : ""}`} />
      {label}
    </Link>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [drawer, setDrawer] = useState(false);
  const status = useWorkerStatus();
  const current = ALL_ITEMS.find((i) => isActive(pathname, i.href));

  return (
    <div className="lg:flex">
      {/* Desktop sidebar */}
      <aside className="hidden lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-60 lg:shrink-0 lg:flex-col lg:border-r lg:border-line lg:bg-surface">
        <div className="px-4 pb-4 pt-5">
          <Logo />
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-4">
          <NavLinks pathname={pathname} />
        </div>
        <div className="border-t border-line p-2">
          <StatusPill {...status} />
        </div>
      </aside>

      {/* Mobile / tablet top bar */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-surface/90 px-4 py-2.5 backdrop-blur lg:hidden">
        <Logo />
        <div className="flex items-center gap-2">
          <span className="hidden text-sm text-ink-2 sm:inline">{current?.label}</span>
          <button
            className="rounded-lg border border-line p-2 text-ink-2 hover:bg-surface-2"
            onClick={() => setDrawer(true)}
            aria-label="Open navigation"
          >
            <Menu size={18} />
          </button>
        </div>
      </header>

      {/* Drawer (all pages) */}
      {drawer && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button className="absolute inset-0 bg-black/60" aria-label="Close navigation" onClick={() => setDrawer(false)} />
          <div className="absolute inset-y-0 right-0 flex w-72 max-w-[85vw] flex-col border-l border-line bg-surface">
            <div className="flex items-center justify-between px-4 py-3">
              <Logo />
              <button className="rounded-lg p-2 text-ink-2 hover:bg-surface-2" onClick={() => setDrawer(false)} aria-label="Close">
                <X size={18} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-2 pb-4">
              <NavLinks pathname={pathname} onNavigate={() => setDrawer(false)} />
            </div>
            <div className="border-t border-line p-2 pb-safe">
              <StatusPill {...status} />
            </div>
          </div>
        </div>
      )}

      <main className="min-w-0 flex-1 px-4 pb-24 pt-5 sm:px-6 lg:px-8 lg:pb-10 lg:pt-7">
        <div className="mx-auto max-w-[1400px]">{children}</div>
      </main>

      {/* Phone bottom tab bar */}
      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-line bg-surface/95 pb-safe backdrop-blur sm:hidden">
        {MOBILE_TABS.map((href) => {
          const item = ALL_ITEMS.find((i) => i.href === href)!;
          const Icon = item.icon;
          const active = isActive(pathname, href);
          return (
            <Link key={href} href={href} className={`flex flex-col items-center gap-0.5 pt-2 text-[10px] ${active ? "text-gold" : "text-ink-3"}`}>
              <Icon size={19} />
              {item.label}
            </Link>
          );
        })}
        <button onClick={() => setDrawer(true)} className="flex flex-col items-center gap-0.5 pt-2 text-[10px] text-ink-3">
          <MoreHorizontal size={19} />
          More
        </button>
      </nav>
    </div>
  );
}

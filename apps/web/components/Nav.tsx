"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/deals", label: "Deals" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/prices", label: "Price history" },
  { href: "/review", label: "Match review" },
  { href: "/sources", label: "Sources" },
  { href: "/health", label: "Collector health" },
  { href: "/settings", label: "Settings" },
];

export default function Nav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <aside className="border-b border-zinc-200 bg-white md:sticky md:top-0 md:h-screen md:w-56 md:shrink-0 md:border-b-0 md:border-r dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center justify-between px-4 py-3 md:py-5">
        <Link href="/" className="font-semibold tracking-tight">
          ⚡ Deal Hunter
        </Link>
        <button
          className="rounded border border-zinc-300 px-2 py-1 text-sm md:hidden dark:border-zinc-700"
          onClick={() => setOpen((o) => !o)}
          aria-label="Toggle navigation"
        >
          ☰
        </button>
      </div>
      <nav className={`${open ? "block" : "hidden"} px-2 pb-3 md:block`}>
        {LINKS.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            onClick={() => setOpen(false)}
            className={`block rounded px-3 py-2 text-sm ${
              isActive(l.href)
                ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                : "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-900"
            }`}
          >
            {l.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}

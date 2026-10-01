import {
  Activity,
  Award,
  Bell,
  BookOpen,
  Crown,
  Eye,
  LayoutDashboard,
  List,
  type LucideIcon,
  Package,
  RadioTower,
  Settings,
  Tag,
  TrendingUp,
  Wallet,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const NAV: { section: string | null; items: NavItem[] }[] = [
  { section: null, items: [{ href: "/", label: "Overview", icon: LayoutDashboard }] },
  {
    section: "Trading",
    items: [
      { href: "/deals", label: "Deals", icon: Tag },
      { href: "/watchlist", label: "Watchlist", icon: Eye },
      { href: "/portfolio", label: "Portfolio", icon: Wallet },
    ],
  },
  {
    section: "Collection",
    items: [
      { href: "/binder/god", label: "GOD Binder", icon: Crown },
      { href: "/binder/collection", label: "Collection", icon: BookOpen },
      { href: "/sealed", label: "Sealed", icon: Package },
      { href: "/grading", label: "Grading", icon: Award },
    ],
  },
  {
    section: "Market",
    items: [
      { href: "/market", label: "Market", icon: TrendingUp },
      { href: "/alerts", label: "Alerts", icon: Bell },
      { href: "/listings", label: "Listings", icon: List },
    ],
  },
  {
    section: "System",
    items: [
      { href: "/sources", label: "Sources", icon: RadioTower },
      { href: "/system", label: "System", icon: Activity },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

/** Bottom tab bar on phones (the rest lives in the "More" drawer). */
export const MOBILE_TABS = ["/", "/deals", "/watchlist", "/portfolio"];

export const ALL_ITEMS = NAV.flatMap((g) => g.items);

export function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

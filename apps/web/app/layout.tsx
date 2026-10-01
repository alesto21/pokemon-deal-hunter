import type { Metadata, Viewport } from "next";
import AppShell from "@/components/shell/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "Deal Hunter",
  description: "Private Pokémon TCG collector and deal command center",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#07080b",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="dark h-full">
      <body className="min-h-full bg-canvas text-ink">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}

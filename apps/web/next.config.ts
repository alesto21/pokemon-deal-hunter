import path from "node:path";
import type { NextConfig } from "next";

const root = path.resolve(".");

const nextConfig: NextConfig = {
  output: "standalone",
  // Lets two dev servers (e.g. QA data + real data) run side by side without sharing .next
  distDir: process.env.NEXT_DIST_DIR || ".next",
  outputFileTracingRoot: root,
  turbopack: { root },
  poweredByHeader: false,
};

export default nextConfig;

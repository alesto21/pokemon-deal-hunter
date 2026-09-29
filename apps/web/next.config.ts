import path from "node:path";
import type { NextConfig } from "next";

const root = path.resolve(".");

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: root,
  turbopack: { root },
  poweredByHeader: false,
};

export default nextConfig;

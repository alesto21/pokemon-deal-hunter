import { NextResponse, type NextRequest } from "next/server";

/**
 * Optional HTTP Basic auth for the whole dashboard.
 * Enabled only when DASHBOARD_PASSWORD is set; /api/health stays open for container healthchecks.
 */
function safeEqual(a: string, b: string): boolean {
  let diff = a.length ^ b.length;
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  }
  return diff === 0;
}

export function proxy(request: NextRequest) {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) return NextResponse.next();
  const user = process.env.DASHBOARD_USER || "admin";
  const header = request.headers.get("authorization") || "";
  if (header.startsWith("Basic ")) {
    try {
      const decoded = atob(header.slice(6));
      const idx = decoded.indexOf(":");
      const u = decoded.slice(0, idx);
      const p = decoded.slice(idx + 1);
      // Evaluate both comparisons to avoid short-circuit timing differences.
      const okUser = safeEqual(u, user);
      const okPass = safeEqual(p, password);
      if (idx >= 0 && okUser && okPass) return NextResponse.next();
    } catch {
      /* fall through to 401 */
    }
  }
  return new NextResponse("Authentication required", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="Pokemon Deal Hunter", charset="UTF-8"' },
  });
}

export const config = {
  matcher: ["/((?!api/health|_next/static|_next/image|favicon.ico).*)"],
};

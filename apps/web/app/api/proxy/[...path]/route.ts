/**
 * Server-side proxy: browser → /api/proxy/<path> → API /api/v1/<path>.
 * The API key is added here and never reaches the browser.
 */
export const dynamic = "force-dynamic";

const SEGMENT = /^[\w.-]+$/;

async function forward(request: Request, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const { path } = await ctx.params;
  if (!path.length || !path.every((s) => SEGMENT.test(s) && s !== ".." && s !== ".")) {
    return Response.json({ detail: "Invalid path" }, { status: 400 });
  }
  const base = (process.env.API_INTERNAL_URL ?? "http://localhost:8000").replace(/\/$/, "");
  const search = new URL(request.url).search;
  const target = `${base}/api/v1/${path.join("/")}${search}`;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  headers.set("accept", request.headers.get("accept") ?? "application/json");
  if (process.env.API_KEY) headers.set("X-API-Key", process.env.API_KEY);

  const hasBody = !["GET", "HEAD"].includes(request.method);
  const init: RequestInit & { duplex?: "half" } = {
    method: request.method,
    headers,
    body: hasBody ? request.body : undefined,
    cache: "no-store",
    redirect: "manual",
  };
  if (hasBody) init.duplex = "half";

  let upstream: Response;
  try {
    upstream = await fetch(target, init);
  } catch {
    return Response.json({ detail: "API unreachable" }, { status: 502 });
  }
  const out = new Headers();
  for (const h of ["content-type", "content-length", "content-disposition", "cache-control"]) {
    const v = upstream.headers.get(h);
    if (v) out.set(h, v);
  }
  return new Response(upstream.status === 204 ? null : upstream.body, { status: upstream.status, headers: out });
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const PUT = forward;
export const DELETE = forward;

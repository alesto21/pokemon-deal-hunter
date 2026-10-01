import { redirect } from "next/navigation";

/** Legacy route: price history now lives on the Market page. */
export default async function PricesRedirect({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const sp = await searchParams;
  const type = typeof sp.type === "string" ? sp.type : null;
  const id = typeof sp.id === "string" ? sp.id : null;
  redirect(type && id && /^\d+$/.test(id) && (type === "card" || type === "product") ? `/market?type=${type}&id=${id}` : "/market");
}

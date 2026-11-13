import { cookies } from "next/headers";

import { hub, hubOn, WS_COOKIE } from "@/lib/tenant";

/* The owner of a business created here sets its own NEAR AI key (or clears it, back to the shared key under
 * its daily cap). The hub checks the session token against the business itself before it changes anything. */
export async function POST(req: Request) {
  const jar = await cookies();
  const slug = jar.get(WS_COOKIE)?.value;
  const token = jar.get("aera_session")?.value;
  if (!hubOn() || !slug || !token) return Response.json({ error: "this is not a business created on this install" }, { status: 404 });
  let key = "";
  try { key = String((await req.json()).key ?? ""); } catch { /* empty clears it */ }
  try {
    const res = await hub(`/tenants/${slug}/key`, { method: "POST", body: JSON.stringify({ key, token }) });
    return Response.json(res.data, { status: res.status });
  } catch {
    return Response.json({ error: "the hub is not responding" }, { status: 503 });
  }
}

import { cookies } from "next/headers";

import { cookieOptions, hub, hubOn, WS_COOKIE } from "@/lib/tenant";

/* Create your own business (hub.py): its own agent service, database and team. The owner is signed in to it
 * straight away and lands on onboarding to describe it. */
export async function GET() {
  if (!hubOn()) return Response.json({ open: false, why_closed: "this install runs one business" });
  try {
    const { data } = await hub<Record<string, unknown>>("/info");
    return Response.json(data);
  } catch {
    return Response.json({ open: false, why_closed: "the hub is not responding" });
  }
}

export async function POST(req: Request) {
  if (!hubOn()) return Response.json({ error: "this install runs one business" }, { status: 404 });
  let res;
  try {
    res = await hub<{ token?: string; user?: unknown; slug?: string; error?: string }>("/tenants", { method: "POST", body: await req.text() });
  } catch {
    return Response.json({ error: "the hub is not responding" }, { status: 503 });
  }
  if (res.status !== 201 || !res.data.token || !res.data.slug) return Response.json(res.data, { status: res.status });
  const jar = await cookies();
  jar.set("aera_session", res.data.token, cookieOptions);
  jar.set(WS_COOKIE, res.data.slug, cookieOptions);
  return Response.json({ user: res.data.user, business: res.data.slug }, { status: 201 });
}

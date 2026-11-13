import { cookies } from "next/headers";

import { cookieOptions, FLAGSHIP, hub, hubOn, tenantBase, WS_COOKIE } from "@/lib/tenant";

/* Sign in. With the hub on, the businesses this email belongs to are tried first (a person's own business
 * before the flagship's demo), then the flagship; the first that accepts the password is the session's
 * business, kept in the aera_ws cookie. */
async function tryLogin(base: string, body: string) {
  const r = await fetch(`${base}/login`, { method: "POST", headers: { "content-type": "application/json" }, body, cache: "no-store" });
  return { ok: r.ok, status: r.status, data: await r.json() };
}

export async function POST(req: Request) {
  const body = await req.text();
  let email = "";
  try { email = String(JSON.parse(body).email ?? ""); } catch { /* the service will say what is wrong */ }
  const candidates: { slug: string | null; base: string }[] = [];
  if (hubOn() && email) {
    try {
      const { data } = await hub<{ tenants: string[] }>(`/resolve?email=${encodeURIComponent(email)}`);
      for (const slug of data.tenants ?? []) {
        const base = await tenantBase(slug);
        if (base) candidates.push({ slug, base });
      }
    } catch { /* the hub is down: the flagship still signs in */ }
  }
  candidates.push({ slug: null, base: FLAGSHIP });

  let last: { status: number; data: { error?: string } } = { status: 401, data: { error: "wrong email or password" } };
  for (const c of candidates) {
    let res;
    try {
      res = await tryLogin(c.base, body);
    } catch {
      last = { status: 503, data: { error: "the agent service is not responding" } };
      continue;
    }
    if (res.ok) {
      const jar = await cookies();
      jar.set("aera_session", res.data.token, cookieOptions);
      if (c.slug) jar.set(WS_COOKIE, c.slug, cookieOptions);
      else jar.delete(WS_COOKIE);
      return Response.json({ user: res.data.user, business: c.slug });
    }
    last = { status: res.status, data: res.data };
  }
  return Response.json(last.data, { status: last.status });
}

export async function DELETE() {
  const jar = await cookies();
  jar.delete("aera_session");
  jar.delete(WS_COOKIE);
  return Response.json({ signedOut: true });
}
